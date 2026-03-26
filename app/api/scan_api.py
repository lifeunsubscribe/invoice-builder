import os
import re
import logging
from flask import Blueprint, jsonify, request

from app.services.folder_service import expand_path, weekly_path

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
