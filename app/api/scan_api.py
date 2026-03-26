import os
import re
import logging
from datetime import date, timedelta
from flask import Blueprint, jsonify, request

from app.services.folder_service import expand_path, weekly_path, read_sidecar

logger = logging.getLogger(__name__)

scan_bp = Blueprint('scan', __name__, url_prefix='/api')


def is_valid_inv_num(inv_num: str) -> bool:
    """
    Validate that invNum follows the expected format: INV-YYYYMMDD.

    This prevents path traversal attacks and ensures input conforms to spec.

    Args:
        inv_num: Invoice number to validate (e.g., "INV-20260324")

    Returns:
        True if valid, False otherwise
    """
    # Pattern: INV- followed by exactly 8 digits (YYYYMMDD)
    pattern = r'^INV-\d{8}$'
    return re.match(pattern, inv_num) is not None


def is_safe_path(base_folder: str, target_path: str) -> bool:
    """
    Verify that target_path is within base_folder to prevent path traversal.

    Args:
        base_folder: The expected base folder (expanded)
        target_path: The full path to validate (expanded)

    Returns:
        True if target_path is safely within base_folder, False otherwise
    """
    # Resolve both paths to absolute, normalized paths
    base_real = os.path.realpath(base_folder)
    target_real = os.path.realpath(target_path)

    # Check if target is within base
    return target_real.startswith(base_real)


@scan_bp.route('/scan', methods=['GET'])
def scan_invoice():
    """
    GET /api/scan?folder=<path>&invNum=<INV-YYYYMMDD>

    Checks whether a specific weekly invoice PDF exists locally.

    Query parameters:
        folder: Base folder path (e.g., "~/Documents/lisa-w-invoices")
        invNum: Invoice number (e.g., "INV-20260324")

    Returns:
        200: {"found": true|false}
        400: {"error": "...", "message": "..."} if params missing or invalid
    """
    # Validate required query parameters
    folder = request.args.get('folder')
    inv_num = request.args.get('invNum')

    if not folder:
        return jsonify({
            "error": "Missing parameter",
            "message": "Query parameter 'folder' is required"
        }), 400

    if not inv_num:
        return jsonify({
            "error": "Missing parameter",
            "message": "Query parameter 'invNum' is required"
        }), 400

    # Validate invNum format to prevent path traversal
    if not is_valid_inv_num(inv_num):
        return jsonify({
            "error": "Invalid parameter",
            "message": "Parameter 'invNum' must match format INV-YYYYMMDD"
        }), 400

    try:
        # Expand tilde and resolve path
        expanded_folder = expand_path(folder)

        # Generate full path to weekly PDF
        pdf_path = weekly_path(expanded_folder, inv_num)

        # Security: verify path is within expected folder to prevent traversal
        if not is_safe_path(expanded_folder, pdf_path):
            logger.warning(
                "Path traversal attempt detected: folder=%s, invNum=%s",
                folder, inv_num
            )
            return jsonify({
                "error": "Invalid path",
                "message": "The specified path is not valid"
            }), 400

        # Check if PDF exists
        found = os.path.exists(pdf_path)

        return jsonify({"found": found}), 200

    except Exception as e:
        logger.exception("Error checking invoice existence: %s", e)
        return jsonify({
            "error": "Server error",
            "message": "An error occurred while checking invoice existence"
        }), 500


def get_weeks_for_month(year: int, month: int) -> list:
    """
    Generate all Tue-Mon weeks that overlap with the given month.

    Weeks start on Tuesday. Only includes weeks where Tuesday falls within
    or after the first day of the month.

    Args:
        year: Year (e.g., 2026)
        month: Month (1-indexed, 1=January, 12=December)

    Returns:
        List of dicts with keys: label, invNum, tuesday, monday
        Example: [
            {
                "label": "Mar 3 – Mar 9, 2026",
                "invNum": "INV-20260303",
                "tuesday": date(2026, 3, 3),
                "monday": date(2026, 3, 9)
            },
            ...
        ]
    """
    # First and last day of the month
    first_day = date(year, month, 1)

    # Last day of month: go to first day of next month, then subtract 1 day
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # Find the Tuesday on or after the first day of the month
    # weekday(): Monday=0, Tuesday=1, ..., Sunday=6
    # If first_day is Wednesday (2), we go forward 6 days to next Tuesday
    # If first_day is Tuesday (1), we start on that day
    # If first_day is Monday (0), we go forward 1 day to Tuesday
    days_until_tuesday = (1 - first_day.weekday()) % 7
    start_day = first_day + timedelta(days=days_until_tuesday)

    weeks = []
    current = start_day

    # Generate weeks until we pass the last day of the month
    while current <= last_day:
        tuesday = current
        monday = current + timedelta(days=6)

        # Format label: "Mar 3 – Mar 9, 2026"
        # Show year only on the end date (Monday)
        tuesday_fmt = tuesday.strftime("%b %-d" if os.name != 'nt' else "%b %d").replace(' 0', ' ')
        monday_fmt = monday.strftime("%b %-d, %Y" if os.name != 'nt' else "%b %d, %Y").replace(' 0', ' ')
        label = f"{tuesday_fmt} – {monday_fmt}"

        # Generate invNum: INV-YYYYMMDD (Tuesday's date)
        inv_num = f"INV-{tuesday.strftime('%Y%m%d')}"

        weeks.append({
            "label": label,
            "invNum": inv_num,
            "tuesday": tuesday,
            "monday": monday
        })

        # Move to next week (7 days forward)
        current += timedelta(days=7)

    return weeks


@scan_bp.route('/scan-month', methods=['GET'])
def scan_month():
    """
    GET /api/scan-month?year=<YYYY>&month=<M>&folder=<path>

    Scan the weekly folder for existing invoices in the given month.
    Returns per-week found status with hours from sidecar JSON files.

    Query parameters:
        year: Year (e.g., 2026)
        month: Month (1-indexed, 1=January, 12=December)
        folder: Base folder path (e.g., "~/Documents/lisa-w-invoices")

    Returns:
        200: {
            "weeks": [
                {
                    "label": "Mar 3 – Mar 9, 2026",
                    "invNum": "INV-20260303",
                    "found": true,
                    "hours": 40
                },
                ...
            ]
        }
        400: {"error": "...", "message": "..."} if params missing or invalid
        500: {"error": "Server error", "message": "..."} on unexpected errors

    Hours field logic:
        - found=false: hours=0 (default for new entries)
        - found=true, sidecar exists: hours=<totalHours from JSON>
        - found=true, no sidecar: hours=null (pre-existing invoice, user enters manually)
    """
    # Validate required query parameters
    year_str = request.args.get('year')
    month_str = request.args.get('month')
    folder = request.args.get('folder')

    if not year_str:
        return jsonify({
            "error": "Missing parameter",
            "message": "Query parameter 'year' is required"
        }), 400

    if not month_str:
        return jsonify({
            "error": "Missing parameter",
            "message": "Query parameter 'month' is required"
        }), 400

    if not folder:
        return jsonify({
            "error": "Missing parameter",
            "message": "Query parameter 'folder' is required"
        }), 400

    # Validate and parse year
    try:
        year = int(year_str)
        if year < 1900 or year > 2100:
            return jsonify({
                "error": "Invalid parameter",
                "message": "Parameter 'year' must be between 1900 and 2100"
            }), 400
    except ValueError:
        return jsonify({
            "error": "Invalid parameter",
            "message": "Parameter 'year' must be a valid integer"
        }), 400

    # Validate and parse month
    try:
        month = int(month_str)
        if month < 1 or month > 12:
            return jsonify({
                "error": "Invalid parameter",
                "message": "Parameter 'month' must be between 1 and 12"
            }), 400
    except ValueError:
        return jsonify({
            "error": "Invalid parameter",
            "message": "Parameter 'month' must be a valid integer"
        }), 400

    try:
        # Expand tilde and resolve path
        expanded_folder = expand_path(folder)

        # Generate weeks for the month
        weeks = get_weeks_for_month(year, month)

        # Build response with found status and hours for each week
        result_weeks = []
        for week in weeks:
            inv_num = week["invNum"]

            # Check if PDF exists
            pdf_path = weekly_path(expanded_folder, inv_num)

            # Security: verify path is within expected folder
            if not is_safe_path(expanded_folder, pdf_path):
                logger.warning(
                    "Path traversal attempt detected in scan-month: folder=%s, invNum=%s",
                    folder, inv_num
                )
                continue  # Skip this week rather than failing entire request

            found = os.path.exists(pdf_path)

            # Determine hours based on found status and sidecar
            if not found:
                hours = 0  # Default for new entries
            else:
                # PDF exists, check for sidecar JSON
                sidecar = read_sidecar(pdf_path)
                if sidecar and 'totalHours' in sidecar:
                    total = sidecar['totalHours']
                    # Validate that totalHours is a number (int or float)
                    if isinstance(total, (int, float)):
                        hours = total
                    else:
                        # Invalid type in sidecar - treat as if no sidecar exists
                        logger.warning(
                            "Invalid totalHours type in sidecar for %s: expected number, got %s",
                            inv_num, type(total).__name__
                        )
                        hours = None
                else:
                    # Pre-existing invoice without sidecar - user enters manually
                    hours = None

            result_weeks.append({
                "label": week["label"],
                "invNum": inv_num,
                "found": found,
                "hours": hours
            })

        return jsonify({"weeks": result_weeks}), 200

    except Exception as e:
        logger.exception("Error scanning month: %s", e)
        return jsonify({
            "error": "Server error",
            "message": "An error occurred while scanning the month"
        }), 500
