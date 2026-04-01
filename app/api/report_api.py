"""
Report API

Endpoint for submitting problem reports and feedback from the app.
"""

import logging
from flask import Blueprint, jsonify, request

from app.services.report_service import send_report

logger = logging.getLogger(__name__)

report_bp = Blueprint('report', __name__)


@report_bp.route('/api/report', methods=['POST'])
def submit_report():
    """
    Submit a problem report or feedback.

    Expects JSON body:
        description: str — user's description of the problem/feedback

    Returns:
        {"success": true} if emailed successfully
        {"success": false, "error": "...", "report": "..."} if email failed
            (frontend uses 'report' field for clipboard fallback)
    """
    data = request.get_json() or {}
    description = (data.get('description') or '').strip()

    if not description:
        return jsonify({"error": "Please describe the issue or feedback"}), 400

    if len(description) > 5000:
        return jsonify({"error": "Description too long (max 5000 characters)"}), 400

    result = send_report(user_description=description)
    return jsonify(result), 200
