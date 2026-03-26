"""
Submit API Blueprint

Handles POST /api/submit/weekly and POST /api/submit/monthly endpoints.
Generates PDFs, saves with sidecar JSON, sends emails, and returns status.
"""

import os
import sys
import json
import logging
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest

from app.services.pdf_service import render_weekly_pdf, render_monthly_pdf
from app.services.mail_service import (
    send_invoice_email,
    create_weekly_email_body,
    create_monthly_email_body
)
from app.services.folder_service import (
    expand_path,
    ensure_folders,
    weekly_path,
    monthly_path,
    write_sidecar
)

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__, url_prefix='/api/submit')


def get_config_path():
    """
    Resolve config.json path for both dev and PyInstaller environments.
    Matches the path resolution logic from config_api.py.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - config.json is next to .exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running in dev mode - config.json is in project root
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.dirname(app_dir)

    return os.path.join(base_dir, 'config.json')


def load_config():
    """
    Load and return config.json contents.

    Returns:
        dict: Configuration data

    Raises:
        FileNotFoundError: if config.json doesn't exist
        json.JSONDecodeError: if config.json is malformed
    """
    config_path = get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@submit_bp.route('/weekly', methods=['POST'])
def submit_weekly():
    """
    POST /api/submit/weekly

    Generate weekly invoice PDF, save with sidecar JSON, send emails.

    Expected JSON payload:
    {
        "hours": {"Monday": 8, "Tuesday": 8, ...},
        "clientEmail": "billing@...",
        "accountantEmail": "accountant@...",
        "week": {
            "start": "March 24",
            "end": "March 30, 2026",
            "invNum": "INV-20260324",
            "dayDates": {"Monday": "Mar 24", ...}
        },
        "template": "morning-light"
    }

    Returns:
        JSON response with success status, saved path, sent emails, and overwrite flag
        200 on success (including partial success if email fails)
        400 on validation errors
        500 on server errors
    """
    try:
        # Parse and validate request
        try:
            payload = request.get_json()
        except BadRequest:
            return jsonify({
                "success": False,
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        if payload is None:
            return jsonify({
                "success": False,
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        # Validate required fields
        required_fields = ['hours', 'clientEmail', 'accountantEmail', 'week', 'template']
        missing_fields = [field for field in required_fields if field not in payload]

        if missing_fields:
            return jsonify({
                "success": False,
                "error": "Missing required fields",
                "message": f"Missing fields: {', '.join(missing_fields)}"
            }), 400

        # Validate week structure
        week = payload['week']
        required_week_fields = ['start', 'end', 'invNum']
        missing_week_fields = [field for field in required_week_fields if field not in week]

        if missing_week_fields:
            return jsonify({
                "success": False,
                "error": "Invalid week data",
                "message": f"Missing week fields: {', '.join(missing_week_fields)}"
            }), 400

        # Load config
        try:
            config = load_config()
        except FileNotFoundError:
            return jsonify({
                "success": False,
                "error": "Configuration not found",
                "message": "config.json does not exist"
            }), 500
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "Invalid configuration",
                "message": "config.json contains malformed JSON"
            }), 500

        # Validate saveFolder in config
        if 'saveFolder' not in config:
            return jsonify({
                "success": False,
                "error": "Configuration error",
                "message": "saveFolder not specified in config.json"
            }), 500

        # Expand saveFolder path (handle ~)
        save_folder = expand_path(config['saveFolder'])

        # Ensure weekly/ folder exists
        try:
            ensure_folders(save_folder)
        except Exception as e:
            logger.exception("Failed to create folders: %s", e)
            return jsonify({
                "success": False,
                "error": "Folder creation failed",
                "message": f"Could not create invoice folders: {str(e)}"
            }), 500

        # Generate PDF path
        inv_num = week['invNum']
        pdf_path = weekly_path(save_folder, inv_num)

        # Check if PDF already exists (for overwrite flag)
        overwrite = os.path.exists(pdf_path)

        # Generate PDF
        try:
            pdf_bytes = render_weekly_pdf(
                config=config,
                hours=payload['hours'],
                week=week,
                template_id=payload['template']
            )
        except ValueError as e:
            # Template validation or config validation error
            return jsonify({
                "success": False,
                "error": "PDF generation failed",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.exception("PDF rendering error: %s", e)
            return jsonify({
                "success": False,
                "error": "PDF generation failed",
                "message": f"Could not generate PDF: {str(e)}"
            }), 500

        # Save PDF to disk
        try:
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.exception("Failed to write PDF: %s", e)
            return jsonify({
                "success": False,
                "error": "File write failed",
                "message": f"Could not save PDF: {str(e)}"
            }), 500

        # Write sidecar JSON with hours data
        try:
            sidecar_data = {
                "totalHours": sum(payload['hours'].values()),
                "dailyHours": payload['hours'],
                "week": week
            }
            write_sidecar(pdf_path, sidecar_data)
        except Exception as e:
            # Non-critical error - log but continue
            logger.warning("Failed to write sidecar JSON: %s", e)

        # Send emails
        recipients = [payload['clientEmail'], payload['accountantEmail']]

        # Calculate totals for email body
        total_hours = sum(payload['hours'].values())
        total_pay = total_hours * config.get('rate', 0)

        email_subject = f"Invoice {inv_num} - {week['start']} to {week['end']}"
        email_body = create_weekly_email_body(
            name=config.get('name', 'Provider'),
            week_start=week['start'],
            week_end=week['end'],
            total_hours=total_hours,
            total_pay=total_pay
        )

        email_result = send_invoice_email(
            recipients=recipients,
            pdf_bytes=pdf_bytes,
            filename=f"{inv_num}.pdf",
            subject=email_subject,
            body=email_body
        )

        # Build response
        if email_result.get('success'):
            # Full success
            return jsonify({
                "success": True,
                "saved": pdf_path,
                "sent": recipients,
                "overwrite": overwrite
            }), 200
        else:
            # Partial success - PDF saved but email failed
            return jsonify({
                "success": True,
                "saved": pdf_path,
                "sent": [],
                "emailError": email_result.get('error', 'Unknown email error'),
                "overwrite": overwrite
            }), 200

    except Exception as e:
        logger.exception("Unexpected error in submit_weekly: %s", e)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500


@submit_bp.route('/monthly', methods=['POST'])
def submit_monthly():
    """
    POST /api/submit/monthly

    Generate monthly report PDF and send to accountant.

    Expected JSON payload:
    {
        "weekData": [
            {"label": "Mar 3 – Mar 9", "hours": 40},
            ...
        ],
        "year": 2026,
        "month": 3,
        "accountantEmail": "accountant@..."
    }

    Returns:
        JSON response with success status, saved path, and sent emails
        200 on success (including partial success if email fails)
        400 on validation errors
        500 on server errors
    """
    try:
        # Parse and validate request
        try:
            payload = request.get_json()
        except BadRequest:
            return jsonify({
                "success": False,
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        if payload is None:
            return jsonify({
                "success": False,
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        # Validate required fields
        required_fields = ['weekData', 'year', 'month', 'accountantEmail']
        missing_fields = [field for field in required_fields if field not in payload]

        if missing_fields:
            return jsonify({
                "success": False,
                "error": "Missing required fields",
                "message": f"Missing fields: {', '.join(missing_fields)}"
            }), 400

        # Load config
        try:
            config = load_config()
        except FileNotFoundError:
            return jsonify({
                "success": False,
                "error": "Configuration not found",
                "message": "config.json does not exist"
            }), 500
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "Invalid configuration",
                "message": "config.json contains malformed JSON"
            }), 500

        # Validate saveFolder in config
        if 'saveFolder' not in config:
            return jsonify({
                "success": False,
                "error": "Configuration error",
                "message": "saveFolder not specified in config.json"
            }), 500

        # Expand saveFolder path
        save_folder = expand_path(config['saveFolder'])

        # Ensure monthly/ folder exists
        try:
            ensure_folders(save_folder)
        except Exception as e:
            logger.exception("Failed to create folders: %s", e)
            return jsonify({
                "success": False,
                "error": "Folder creation failed",
                "message": f"Could not create invoice folders: {str(e)}"
            }), 500

        # Generate month label (e.g., "March 2026")
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        month_label = f"{month_names[payload['month'] - 1]} {payload['year']}"

        # Generate PDF path
        pdf_path = monthly_path(save_folder, payload['year'], payload['month'])

        # Generate PDF
        try:
            pdf_bytes = render_monthly_pdf(
                config=config,
                week_data=payload['weekData'],
                month_label=month_label
            )
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "PDF generation failed",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.exception("PDF rendering error: %s", e)
            return jsonify({
                "success": False,
                "error": "PDF generation failed",
                "message": f"Could not generate PDF: {str(e)}"
            }), 500

        # Save PDF to disk
        try:
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.exception("Failed to write PDF: %s", e)
            return jsonify({
                "success": False,
                "error": "File write failed",
                "message": f"Could not save PDF: {str(e)}"
            }), 500

        # Send email to accountant only
        recipients = [payload['accountantEmail']]

        # Calculate totals for email body
        total_hours = sum(week.get('hours', 0) for week in payload['weekData'])
        total_pay = total_hours * config.get('rate', 0)

        email_subject = f"Monthly Report - {month_label}"
        email_body = create_monthly_email_body(
            name=config.get('name', 'Provider'),
            month_label=month_label,
            total_hours=total_hours,
            total_pay=total_pay
        )

        email_result = send_invoice_email(
            recipients=recipients,
            pdf_bytes=pdf_bytes,
            filename=os.path.basename(pdf_path),
            subject=email_subject,
            body=email_body
        )

        # Build response
        if email_result.get('success'):
            # Full success
            return jsonify({
                "success": True,
                "saved": pdf_path,
                "sent": recipients
            }), 200
        else:
            # Partial success - PDF saved but email failed
            return jsonify({
                "success": True,
                "saved": pdf_path,
                "sent": [],
                "emailError": email_result.get('error', 'Unknown email error')
            }), 200

    except Exception as e:
        logger.exception("Unexpected error in submit_monthly: %s", e)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500
