import os
import re
import json
import logging
from flask import Blueprint, jsonify, request

from app.api.config_api import get_config_path, get_or_create_config
from app.services.folder_service import expand_path, ensure_folders, logs_path

logger = logging.getLogger(__name__)

log_bp = Blueprint('log', __name__, url_prefix='/api')

DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Matches bare timestamp lines like "10:32 am — " with nothing after the dash
BARE_TIMESTAMP = re.compile(r'^(\d{1,2}:\d{2}\s*[ap]m\s*—\s*)+$', re.IGNORECASE | re.MULTILINE)
DEFAULT_SECTIONS = []
MAX_LOG_SIZE = 512 * 1024  # 512KB


def _load_config():
    """Load and return config dict, or None on error."""
    config_path = get_config_path()
    get_or_create_config(config_path)
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        logger.exception("Failed to load config: %s", e)
        return None


def _save_config(config_data):
    """Write config dict back to disk (reuses config_api write pattern)."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        # In dev mode the config_path is already the project root config.
        # In frozen mode with a save folder, also write there.
        save_folder = config_data.get('saveFolder', '')
        if save_folder:
            expanded = expand_path(save_folder)
            folder_config = os.path.join(expanded, 'config.json')
            if os.path.abspath(folder_config) != os.path.abspath(config_path):
                with open(folder_config, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.exception("Failed to save config: %s", e)
        raise


@log_bp.route('/log', methods=['GET'])
def get_log():
    """
    GET /api/log?date=YYYY-MM-DD

    Returns the daily service log for the given date.
    Returns an empty template if no log exists yet.
    """
    date_str = request.args.get('date', '')
    if not DATE_PATTERN.match(date_str):
        return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400

    config = _load_config()
    if not config or not config.get('saveFolder'):
        return jsonify({"date": date_str, "sections": []}), 200

    save_folder = expand_path(config['saveFolder'])

    try:
        path = logs_path(save_folder, date_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data), 200
    except FileNotFoundError:
        return jsonify({"date": date_str, "sections": []}), 200
    except json.JSONDecodeError:
        logger.warning("Corrupt log file: %s", path)
        return jsonify({"error": "Log file is corrupt"}), 500
    except OSError as e:
        logger.exception("Error reading log: %s", e)
        return jsonify({"error": "Failed to read log"}), 500


TIME_PATTERN = re.compile(r'^\d{2}:\d{2}$')
VITALS_KEYS = {'temperature', 'bpSystolic', 'bpDiastolic', 'weight', 'pulse', 'o2sat'}


def _validate_vitals(vitals):
    """Validate vitals object. Returns error string or None."""
    if not isinstance(vitals, dict):
        return "vitals must be an object"
    for key in vitals:
        if key not in VITALS_KEYS:
            return f"Unknown vitals key: {key}"
        val = vitals[key]
        if val is not None and not isinstance(val, (int, float)):
            return f"vitals.{key} must be a number or null"
    return None


def _validate_meds(meds):
    """Validate meds array. Returns error string or None."""
    if not isinstance(meds, list):
        return "meds must be a list"
    for m in meds:
        if not isinstance(m, dict):
            return "Each med must be an object"
        if not isinstance(m.get('name', ''), str):
            return "Med name must be a string"
        times = m.get('times', [])
        if not isinstance(times, list) or not all(isinstance(t, str) for t in times):
            return "Med times must be a list of strings"
    return None


def _validate_shift(shift):
    """Validate shift object. Returns error string or None."""
    if not isinstance(shift, dict):
        return "shift must be an object"
    for key in ('start', 'end'):
        val = shift.get(key, '')
        if val and not TIME_PATTERN.match(val):
            return f"shift.{key} must be HH:MM format"
    return None


@log_bp.route('/log', methods=['POST'])
def save_log():
    """
    POST /api/log

    Saves a daily service log. Expects JSON:
    {"date": "YYYY-MM-DD", "sections": [...], "vitals": {...}, "meds": [...], "shift": {...}, "clientId": "..."}
    Only date and sections are required; vitals, meds, shift, clientId are optional.
    """
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    date_str = data.get('date', '')
    if not DATE_PATTERN.match(date_str):
        return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400

    sections = data.get('sections')
    if not isinstance(sections, list):
        return jsonify({"error": "sections must be a list"}), 400

    for s in sections:
        if not isinstance(s, dict) or 'name' not in s or 'content' not in s:
            return jsonify({"error": "Each section must have name and content"}), 400
        if not isinstance(s['name'], str) or not isinstance(s['content'], str):
            return jsonify({"error": "Section name and content must be strings"}), 400

    # Validate optional structured fields
    if 'vitals' in data:
        err = _validate_vitals(data['vitals'])
        if err:
            return jsonify({"error": err}), 400

    if 'meds' in data:
        err = _validate_meds(data['meds'])
        if err:
            return jsonify({"error": err}), 400

    if 'shift' in data:
        err = _validate_shift(data['shift'])
        if err:
            return jsonify({"error": err}), 400

    if 'clientId' in data and not isinstance(data['clientId'], str):
        return jsonify({"error": "clientId must be a string"}), 400

    # Size guard
    serialized = json.dumps(data)
    if len(serialized.encode('utf-8')) > MAX_LOG_SIZE:
        return jsonify({"error": "Log data exceeds maximum size (512KB)"}), 400

    config = _load_config()
    if not config or not config.get('saveFolder'):
        return jsonify({"error": "No save folder configured"}), 400

    save_folder = expand_path(config['saveFolder'])

    try:
        ensure_folders(save_folder)
        path = logs_path(save_folder, date_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"success": True}), 200
    except OSError as e:
        logger.exception("Error writing log: %s", e)
        return jsonify({"error": "Failed to save log"}), 500


@log_bp.route('/log-sections', methods=['GET'])
def get_log_sections():
    """
    GET /api/log-sections

    Returns the user's custom section names for daily logs.
    Falls back to defaults if not configured.
    """
    config = _load_config()
    sections = (config or {}).get('logSections', DEFAULT_SECTIONS)
    return jsonify({"sections": sections}), 200


@log_bp.route('/log-sections', methods=['POST'])
def save_log_sections():
    """
    POST /api/log-sections

    Saves custom section names. Expects {"sections": ["Vitals", ...]}.
    """
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    sections = data.get('sections')
    if not isinstance(sections, list):
        return jsonify({"error": "sections must be a list"}), 400

    for s in sections:
        if not isinstance(s, str) or not s.strip():
            return jsonify({"error": "Each section must be a non-empty string"}), 400

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in sections:
        s_stripped = s.strip()
        if s_stripped not in seen:
            seen.add(s_stripped)
            unique.append(s_stripped)

    config = _load_config()
    if not config:
        return jsonify({"error": "Failed to load config"}), 500

    config['logSections'] = unique

    try:
        _save_config(config)
        return jsonify({"success": True}), 200
    except OSError:
        return jsonify({"error": "Failed to save config"}), 500


@log_bp.route('/log-dates', methods=['GET'])
def get_log_dates():
    """
    GET /api/log-dates?year=YYYY&month=MM

    Returns a list of dates (DD) in the given month that have log files.
    Used by the calendar picker to highlight days with data.
    """
    try:
        year = int(request.args.get('year', 0))
        month = int(request.args.get('month', 0))
    except (ValueError, TypeError):
        return jsonify({"error": "year and month must be integers"}), 400

    if not (1900 <= year <= 9999 and 1 <= month <= 12):
        return jsonify({"error": "Invalid year/month"}), 400

    config = _load_config()
    if not config or not config.get('saveFolder'):
        return jsonify({"dates": []}), 200

    save_folder = expand_path(config['saveFolder'])
    logs_dir = os.path.join(save_folder, "logs")

    if not os.path.isdir(logs_dir):
        return jsonify({"dates": []}), 200

    prefix = f"LOG-{year}-{str(month).zfill(2)}-"
    dates = []
    try:
        for fname in os.listdir(logs_dir):
            if fname.startswith(prefix) and fname.endswith(".json"):
                day_str = fname[len(prefix):-5]  # extract DD
                if day_str.isdigit():
                    # Only include if at least one section has real content
                    fpath = os.path.join(logs_dir, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        has_content = False
                        # Check text sections (ignore bare timestamps)
                        sections = data.get("sections", [])
                        for s in sections:
                            text = s.get("content", "").strip()
                            if text and BARE_TIMESTAMP.sub("", text).strip():
                                has_content = True
                                break
                        # Check vitals
                        vitals = data.get("vitals", {})
                        if any(v is not None for v in vitals.values()):
                            has_content = True
                        # Check meds with recorded times
                        meds = data.get("meds", [])
                        if any(m.get("times") for m in meds):
                            has_content = True
                        # Check shift times
                        shift = data.get("shift", {})
                        if shift.get("start") or shift.get("end"):
                            has_content = True
                        if has_content:
                            dates.append(int(day_str))
                    except (json.JSONDecodeError, OSError):
                        pass
    except OSError as e:
        logger.warning("Error scanning logs dir: %s", e)

    return jsonify({"dates": sorted(dates)}), 200


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@log_bp.route('/log-week', methods=['GET'])
def get_log_week():
    """
    GET /api/log-week?monday=YYYY-MM-DD

    Returns hours computed from shift times for Mon-Fri of the given week.
    Used to auto-populate weekly invoice hours from daily logs.
    """
    monday_str = request.args.get('monday', '')
    if not DATE_PATTERN.match(monday_str):
        return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400

    config = _load_config()
    if not config or not config.get('saveFolder'):
        hours = {day: 0 for day in WEEKDAY_NAMES}
        has_log = {day: False for day in WEEKDAY_NAMES}
        return jsonify({"hours": hours, "hasLog": has_log}), 200

    save_folder = expand_path(config['saveFolder'])

    # Parse monday date
    from datetime import datetime, timedelta
    try:
        monday = datetime.strptime(monday_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400

    hours = {}
    has_log = {}

    for i, day_name in enumerate(WEEKDAY_NAMES[:7]):
        date = monday + timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')

        try:
            path = logs_path(save_folder, date_str)
        except ValueError:
            hours[day_name] = 0
            has_log[day_name] = False
            continue

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            shift = data.get('shift', {})
            start = shift.get('start', '')
            end = shift.get('end', '')
            if start and end:
                try:
                    sh, sm = map(int, start.split(':'))
                    eh, em = map(int, end.split(':'))
                    diff = (eh * 60 + em) - (sh * 60 + sm)
                    hours[day_name] = round(max(0, diff) / 60, 1)
                except (ValueError, TypeError):
                    hours[day_name] = 0
            else:
                hours[day_name] = 0
            has_log[day_name] = True
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            hours[day_name] = 0
            has_log[day_name] = False

    return jsonify({"hours": hours, "hasLog": has_log}), 200
