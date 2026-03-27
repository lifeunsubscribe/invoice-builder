"""
Submit API Blueprint

Handles POST /api/submit/weekly and POST /api/submit/monthly endpoints.
Generates PDFs, saves with sidecar JSON, sends emails, and returns status.
"""

import os
import sys
import json
import logging
import re
from datetime import datetime, timedelta
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
from app.middleware.rate_limiter import limiter, SUBMIT_RATE_LIMIT
from app.middleware.request_validator import validate_array_size

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__, url_prefix='/api/submit')

# Basic email validation pattern
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def is_valid_email(email):
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        bool: True if email format is valid, False otherwise
    """
    if not isinstance(email, str):
        return False
    return EMAIL_PATTERN.match(email) is not None


def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal attacks.

    Args:
        filename: The filename to sanitize

    Returns:
        str: Sanitized filename with path separators and parent references removed

    Raises:
        ValueError: If the filename is empty after sanitization
    """
    if not isinstance(filename, str):
        raise ValueError("Filename must be a string")

    # Remove any path separators and parent directory references
    sanitized = filename.replace('/', '').replace('\\', '').replace('..', '')

    # Remove any other potentially dangerous characters
    sanitized = re.sub(r'[^\w\-.]', '', sanitized)

    if not sanitized:
        raise ValueError("Invalid filename: filename is empty after sanitization")

    return sanitized


def get_config_path():
    """
    Resolve config.json path. Uses the same logic as config_api.py.
    """
    from app.api.config_api import get_config_path as _get_config_path
    return _get_config_path()


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
        config = json.load(f)
    # Ensure rate is numeric (may be stored as string from form input)
    try:
        config['rate'] = float(config.get('rate', 0))
    except (ValueError, TypeError):
        config['rate'] = 0.0
    return config


@submit_bp.route('/weekly', methods=['POST'])
@limiter.limit(SUBMIT_RATE_LIMIT)
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
        required_fields = ['hours', 'week', 'template']
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

        # Validate email addresses (only if provided and non-empty)
        client_email = payload.get('clientEmail', '').strip()
        accountant_email = payload.get('accountantEmail', '').strip()

        if client_email and not is_valid_email(client_email):
            return jsonify({
                "success": False,
                "error": "Invalid email",
                "message": "clientEmail must be a valid email address"
            }), 400

        if accountant_email and not is_valid_email(accountant_email):
            return jsonify({
                "success": False,
                "error": "Invalid email",
                "message": "accountantEmail must be a valid email address"
            }), 400

        # Validate hours values are numeric
        if not isinstance(payload['hours'], dict):
            return jsonify({
                "success": False,
                "error": "Invalid hours data",
                "message": "hours must be a dictionary"
            }), 400

        # Validate hours dictionary size to prevent DoS
        try:
            validate_array_size(payload['hours'], 'hours')
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid hours data",
                "message": str(e)
            }), 400

        for day, hours in payload['hours'].items():
            if not isinstance(hours, (int, float)):
                return jsonify({
                    "success": False,
                    "error": "Invalid hours value",
                    "message": f"hours value for {day} must be a number"
                }), 400

        # Load config
        try:
            config = load_config()
        except FileNotFoundError:
            return jsonify({
                "success": False,
                "error": "Please fill out your profile in Edit Profile before submitting.",
                "message": "config.json does not exist"
            }), 400
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "Your profile settings are invalid. Please re-enter your details in Edit Profile.",
                "message": "config.json contains malformed JSON"
            }), 400

        # Validate saveFolder in config
        if 'saveFolder' not in config or not config['saveFolder']:
            return jsonify({
                "success": False,
                "error": "Please set a save folder in Edit Profile before submitting.",
                "message": "saveFolder not specified in config.json"
            }), 400

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

        # Sanitize and validate invoice number to prevent path traversal
        try:
            inv_num = sanitize_filename(week['invNum'])
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid invoice number",
                "message": str(e)
            }), 400

        # Generate PDF path
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
            # Missing config keys means profile is incomplete
            error_str = str(e)
            if "Missing required config keys" in error_str:
                error_msg = "Please fill out your profile in Edit Profile before submitting."
            else:
                error_msg = error_str
            return jsonify({
                "success": False,
                "error": error_msg,
                "message": error_str
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
                "week": week,
                "template": payload.get('template', 'morning-light')
            }
            write_sidecar(pdf_path, sidecar_data)
        except Exception as e:
            # Non-critical error - log but continue
            logger.warning("Failed to write sidecar JSON: %s", e)

        # Send emails (only if recipients provided)
        recipients = [e for e in [client_email, accountant_email] if e]

        if recipients:
            # Calculate totals for email body
            total_hours = sum(payload['hours'].values())
            total_pay = total_hours * config.get('rate', 0)

            # Compute worked date range (only days with hours > 0)
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            monday_date = datetime.strptime(inv_num.replace('INV-', ''), '%Y%m%d')
            worked_days = [i for i, day in enumerate(day_order) if payload['hours'].get(day, 0) > 0]

            if worked_days:
                first_worked = monday_date + timedelta(days=worked_days[0])
                last_worked = monday_date + timedelta(days=worked_days[-1])
                work_start = f"{first_worked.strftime('%B')} {first_worked.day}"
                work_end = f"{last_worked.strftime('%B')} {last_worked.day}, {last_worked.year}"
            else:
                work_start = week['start']
                work_end = week['end']

            email_subject = f"Invoice {inv_num} - {work_start} to {work_end}"
            email_body = create_weekly_email_body(
                name=config.get('name', 'Provider'),
                week_start=work_start,
                week_end=work_end,
                total_hours=total_hours,
                total_pay=total_pay
            )

            try:
                email_result = send_invoice_email(
                    recipients=recipients,
                    pdf_bytes=pdf_bytes,
                    filename=f"{inv_num}.pdf",
                    subject=email_subject,
                    body=email_body
                )
            except Exception as e:
                logger.exception("Email sending failed: %s", e)
                email_result = {'success': False, 'error': str(e)}

            # Build response
            if email_result.get('success'):
                return jsonify({
                    "success": True,
                    "saved": pdf_path,
                    "sent": recipients,
                    "overwrite": overwrite
                }), 200
            else:
                return jsonify({
                    "success": True,
                    "saved": pdf_path,
                    "sent": [],
                    "emailError": email_result.get('error', 'Unknown email error'),
                    "overwrite": overwrite
                }), 200

        # No recipients - just save PDF
        return jsonify({
            "success": True,
            "saved": pdf_path,
            "sent": [],
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
@limiter.limit(SUBMIT_RATE_LIMIT)
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
        required_fields = ['weekData', 'year', 'month']
        missing_fields = [field for field in required_fields if field not in payload]

        if missing_fields:
            return jsonify({
                "success": False,
                "error": "Missing required fields",
                "message": f"Missing fields: {', '.join(missing_fields)}"
            }), 400

        # Validate email address (only if provided and non-empty)
        accountant_email = payload.get('accountantEmail', '').strip()

        if accountant_email and not is_valid_email(accountant_email):
            return jsonify({
                "success": False,
                "error": "Invalid email",
                "message": "accountantEmail must be a valid email address"
            }), 400

        # Validate weekData is an array
        if not isinstance(payload['weekData'], list):
            return jsonify({
                "success": False,
                "error": "Invalid weekData",
                "message": "weekData must be an array"
            }), 400

        # Validate weekData array size to prevent DoS
        try:
            validate_array_size(payload['weekData'], 'weekData')
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid weekData",
                "message": str(e)
            }), 400

        # Validate weekData array elements
        for i, week in enumerate(payload['weekData']):
            if not isinstance(week, dict):
                return jsonify({
                    "success": False,
                    "error": "Invalid weekData element",
                    "message": f"weekData[{i}] must be an object"
                }), 400

            if 'label' not in week:
                return jsonify({
                    "success": False,
                    "error": "Invalid weekData element",
                    "message": f"weekData[{i}] missing required field 'label'"
                }), 400

            if 'hours' not in week:
                return jsonify({
                    "success": False,
                    "error": "Invalid weekData element",
                    "message": f"weekData[{i}] missing required field 'hours'"
                }), 400

            if not isinstance(week['hours'], (int, float)):
                return jsonify({
                    "success": False,
                    "error": "Invalid weekData element",
                    "message": f"weekData[{i}].hours must be a number"
                }), 400

            if not isinstance(week['label'], str):
                return jsonify({
                    "success": False,
                    "error": "Invalid weekData element",
                    "message": f"weekData[{i}].label must be a string"
                }), 400

        # Validate year
        if not isinstance(payload['year'], int) or payload['year'] < 1900 or payload['year'] > 2200:
            return jsonify({
                "success": False,
                "error": "Invalid year",
                "message": "year must be an integer between 1900 and 2200"
            }), 400

        # Validate month range
        if not isinstance(payload['month'], int) or payload['month'] < 1 or payload['month'] > 12:
            return jsonify({
                "success": False,
                "error": "Invalid month",
                "message": "month must be an integer between 1 and 12"
            }), 400

        # Load config
        try:
            config = load_config()
        except FileNotFoundError:
            return jsonify({
                "success": False,
                "error": "Please fill out your profile in Edit Profile before submitting.",
                "message": "config.json does not exist"
            }), 400
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "Your profile settings are invalid. Please re-enter your details in Edit Profile.",
                "message": "config.json contains malformed JSON"
            }), 400

        # Validate saveFolder in config
        if 'saveFolder' not in config or not config['saveFolder']:
            return jsonify({
                "success": False,
                "error": "Please set a save folder in Edit Profile before submitting.",
                "message": "saveFolder not specified in config.json"
            }), 400

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

        # Check if PDF already exists (for overwrite flag)
        overwrite = os.path.exists(pdf_path)

        # Generate PDF
        try:
            pdf_bytes = render_monthly_pdf(
                config=config,
                week_data=payload['weekData'],
                month_label=month_label
            )
        except ValueError as e:
            error_str = str(e)
            if "Missing required config keys" in error_str:
                error_msg = "Please fill out your profile in Edit Profile before submitting."
            else:
                error_msg = error_str
            return jsonify({
                "success": False,
                "error": error_msg,
                "message": error_str
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

        # Send email to accountant (only if provided)
        if accountant_email:
            recipients = [accountant_email]

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

            try:
                email_result = send_invoice_email(
                    recipients=recipients,
                    pdf_bytes=pdf_bytes,
                    filename=os.path.basename(pdf_path),
                    subject=email_subject,
                    body=email_body
                )
            except Exception as e:
                logger.exception("Email sending failed: %s", e)
                email_result = {'success': False, 'error': str(e)}

            # Build response
            if email_result.get('success'):
                return jsonify({
                    "success": True,
                    "saved": pdf_path,
                    "sent": recipients,
                    "overwrite": overwrite
                }), 200
            else:
                return jsonify({
                    "success": True,
                    "saved": pdf_path,
                    "sent": [],
                    "emailError": email_result.get('error', 'Unknown email error'),
                    "overwrite": overwrite
                }), 200

        # No recipient - just save PDF
        return jsonify({
            "success": True,
            "saved": pdf_path,
            "sent": [],
            "overwrite": overwrite
        }), 200

    except Exception as e:
        logger.exception("Unexpected error in submit_monthly: %s", e)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500
