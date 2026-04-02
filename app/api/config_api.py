import os
import sys
import json
import logging
from flask import Blueprint, jsonify, request
from app.themes import get_all_themes, get_chrome_palette, THEME_ORDER

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__, url_prefix='/api')

def _appdata_dir():
    """Return the app data directory for storing the save folder pointer."""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    else:
        base = os.path.expanduser('~')
    d = os.path.join(base, '.invoicebuilder')
    os.makedirs(d, exist_ok=True)
    return d


def _dev_base_dir():
    """Return the project root in dev mode."""
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(app_dir)


def get_config_path():
    """
    Resolve config.json path. Reads a pointer file from app data to find
    the save folder, then loads config from there. Falls back to project
    root (dev) or app data dir (frozen).
    """
    # In dev mode, use project root config.json directly
    if not getattr(sys, 'frozen', False):
        return os.path.join(_dev_base_dir(), 'config.json')

    # In frozen mode, check the pointer file for saveFolder
    pointer_path = os.path.join(_appdata_dir(), 'pointer.json')
    try:
        with open(pointer_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        save_folder = data.get('saveFolder', '')
        if save_folder:
            expanded = os.path.expanduser(save_folder)
            folder_config = os.path.join(expanded, 'config.json')
            if os.path.exists(folder_config):
                return folder_config
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    # Fallback: config in app data dir
    return os.path.join(_appdata_dir(), 'config.json')

def derive_save_folder(full_name):
    """
    Derive save folder path from user's full name.

    Logic matches frontend deriveSaveFolder (App.jsx lines 26-32):
    - Split name by whitespace, filter empty strings
    - If less than 2 parts (single name): ~/Documents/{name}-invoices
    - Otherwise: ~/Documents/{first}-{last-initial}-invoices

    Examples:
    - "Lisa Wadley" -> "~/Documents/lisa-w-invoices"
    - "Lisa Marie Wadley" -> "~/Documents/lisa-w-invoices"
    - "Jane" -> "~/Documents/jane-invoices"
    """
    parts = full_name.strip().split()
    parts = [p for p in parts if p]  # Filter empty strings

    if len(parts) < 2:
        # Single name edge case
        name = (parts[0] if parts else "user").lower()
        return f"~/Documents/{name}-invoices"

    # Multiple parts: first name + first letter of last part
    first = parts[0].lower()
    last = parts[-1]
    return f"~/Documents/{first}-{last[0].lower()}-invoices"

DEFAULT_CONFIG = {
    "name": "",
    "address": "",
    "personalEmail": "",
    "rate": 0,
    "clientName": "",
    "clientEmail": "",
    "accountantEmail": "",
    "template": "morning-light",
    "accent": "#c47a86",
    "patientName": "",
    "patientAddress": "",
    "invoiceNote": "",
    "saveFolder": "",
    "logSections": [],
    "clients": [],
    "activeClientId": "",
    "signatureFont": "",
    "enabledVitals": ["temperature", "bpSystolic", "bpDiastolic", "weight", "pulse", "o2sat"],
    "occupation": "",
    "agency": ""
}


def get_or_create_config(config_path):
    """Create config.json with empty defaults if it doesn't exist."""
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)


def _migrate_config(config_data):
    """
    Migrate older config formats forward. Currently handles:
    - Moving flat patientName/patientAddress into a clients[] array
    - Ensuring new fields exist with defaults
    Returns True if the config was modified and should be saved.
    """
    changed = False

    # Ensure new fields exist
    for key, default in [("template", "morning-light"), ("clients", []), ("activeClientId", ""), ("signatureFont", ""),
                         ("enabledVitals", ["temperature", "bpSystolic", "bpDiastolic", "weight", "pulse", "o2sat"]),
                         ("occupation", ""), ("agency", "")]:
        if key not in config_data:
            config_data[key] = default
            changed = True

    # Migrate flat patient fields to clients array
    flat_name = config_data.get("patientName", "").strip()
    flat_addr = config_data.get("patientAddress", "").strip()
    clients = config_data.get("clients", [])

    if not clients and flat_name:
        # No clients array yet — create from flat fields
        config_data["clients"] = [{
            "id": "client-1",
            "name": flat_name,
            "address": flat_addr,
            "objective": "",
            "defaultShift": {"start": "09:00", "end": "17:00"},
            "meds": []
        }]
        config_data["activeClientId"] = "client-1"
        changed = True
    elif clients and flat_name:
        # Clients array exists — if the active client has no name but flat fields
        # do, backfill (handles case where client card was added but not populated)
        active_id = config_data.get("activeClientId", "")
        active = next((c for c in clients if c.get("id") == active_id), clients[0] if clients else None)
        if active and not active.get("name", "").strip():
            active["name"] = flat_name
            if flat_addr and not active.get("address", "").strip():
                active["address"] = flat_addr
            changed = True

    # Auto-detect occupation for existing HHA users (have patient data, no occupation set)
    if not config_data.get("occupation") and (flat_name or any(c.get("name") for c in config_data.get("clients", []))):
        config_data["occupation"] = "home-health-aide"
        changed = True

    # Seed default log sections for HHA if empty
    if config_data.get("occupation") == "home-health-aide" and not config_data.get("logSections"):
        config_data["logSections"] = ["Food", "Activities", "Travel", "Visitors", "Comments"]
        changed = True

    return changed


def _sync_flat_patient_fields(config_data):
    """
    Sync flat patientName/patientAddress from the active client so that
    invoice templates (which reference config.patientName) keep working.
    """
    clients = config_data.get("clients", [])
    active_id = config_data.get("activeClientId", "")
    client = None
    for c in clients:
        if c.get("id") == active_id:
            client = c
            break
    if not client and clients:
        client = clients[0]
    if client:
        config_data["patientName"] = client.get("name", "")
        config_data["patientAddress"] = client.get("address", "")

@config_bp.route('/themes', methods=['GET'])
def get_themes():
    """
    GET /api/themes

    Returns ordered list of theme chrome palettes for the frontend UI.
    """
    return jsonify([get_chrome_palette(tid) for tid in THEME_ORDER]), 200


@config_bp.route('/config', methods=['GET'])
def get_config():
    """
    GET /api/config

    Returns the contents of config.json.
    Creates config from example on first run if missing.
    """
    config_path = get_config_path()
    get_or_create_config(config_path)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # Auto-migrate older config formats
        if _migrate_config(config_data):
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
            except OSError:
                pass  # Migration is best-effort; still return the data

        return jsonify(config_data), 200
    except PermissionError as e:
        logger.exception("Permission denied reading config file: %s", e)
        return jsonify({
            "error": "Permission denied",
            "message": "Cannot read configuration file due to insufficient permissions"
        }), 500
    except json.JSONDecodeError:
        return jsonify({
            "error": "Invalid JSON in configuration file",
            "message": "The configuration file contains malformed JSON"
        }), 500
    except OSError as e:
        logger.exception("OS error reading config file: %s", e)
        return jsonify({
            "error": "File system error",
            "message": "An error occurred reading the configuration file"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error reading config file: %s", e)
        return jsonify({
            "error": "Failed to read configuration",
            "message": "An unexpected error occurred while reading the configuration file"
        }), 500

@config_bp.route('/config', methods=['POST'])
def update_config():
    """
    POST /api/config

    Accepts JSON payload and writes it to config.json.
    Returns 400 for invalid JSON, 500 for write errors.
    """
    config_path = get_config_path()

    try:
        # Flask automatically parses JSON if Content-Type is application/json
        # request.json will be None if parsing fails
        config_data = request.get_json()

        if config_data is None:
            return jsonify({
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        # Validate that config is a dict (not array or primitive)
        if not isinstance(config_data, dict):
            return jsonify({
                "error": "Invalid configuration format",
                "message": "Configuration must be a JSON object"
            }), 400

        # Add size limit (1MB) to prevent abuse
        config_json = json.dumps(config_data)
        if len(config_json.encode('utf-8')) > 1024 * 1024:
            return jsonify({
                "error": "Configuration too large",
                "message": "Configuration must be less than 1MB"
            }), 400

        # Validate template ID if present
        template = config_data.get('template', '')
        if template and template not in THEME_ORDER:
            config_data['template'] = 'morning-light'

        # Sync flat patient fields from active client for template compat
        _sync_flat_patient_fields(config_data)

        # Seed default log sections when occupation is set and sections are empty
        OCC_DEFAULT_SECTIONS = {
            "home-health-aide": ["Food", "Activities", "Travel", "Visitors", "Comments"],
        }
        occ = config_data.get("occupation", "")
        if occ in OCC_DEFAULT_SECTIONS and not config_data.get("logSections"):
            config_data["logSections"] = OCC_DEFAULT_SECTIONS[occ]

        # Find the old save folder (before this save) so we can detect moves
        old_save_folder = ''
        try:
            old_config_path = get_config_path()
            with open(old_config_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            old_save_folder = old_data.get('saveFolder', '')
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        # Write config to the save folder
        save_folder = config_data.get('saveFolder', '')
        if save_folder:
            expanded = os.path.expanduser(save_folder)
            os.makedirs(expanded, exist_ok=True)
            folder_config = os.path.join(expanded, 'config.json')
            with open(folder_config, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            # If save folder changed, remove config from the old location
            if old_save_folder and old_save_folder != save_folder:
                old_expanded = os.path.expanduser(old_save_folder)
                old_config = os.path.join(old_expanded, 'config.json')
                try:
                    if os.path.exists(old_config):
                        os.remove(old_config)
                except OSError:
                    pass  # Best effort — don't fail the save

        # Write pointer to app data so the app can find the save folder
        if save_folder and getattr(sys, 'frozen', False):
            pointer_path = os.path.join(_appdata_dir(), 'pointer.json')
            with open(pointer_path, 'w', encoding='utf-8') as f:
                json.dump({"saveFolder": save_folder}, f, indent=2)
        elif not getattr(sys, 'frozen', False):
            # Dev mode: also write to project root
            dev_config = os.path.join(_dev_base_dir(), 'config.json')
            with open(dev_config, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

        return jsonify({
            "success": True,
            "message": "Configuration saved successfully"
        }), 200

    except PermissionError as e:
        logger.exception("Permission denied writing config file: %s", e)
        return jsonify({
            "error": "Permission denied",
            "message": "Cannot write configuration file due to insufficient permissions"
        }), 500
    except OSError as e:
        logger.exception("OS error writing config file: %s", e)
        return jsonify({
            "error": "File system error",
            "message": "An error occurred writing the configuration file (disk may be full)"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error writing config file: %s", e)
        return jsonify({
            "error": "Failed to write configuration",
            "message": "An unexpected error occurred while saving the configuration"
        }), 500
