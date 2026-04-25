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

from app.services.pdf_service import (
    render_weekly_pdf, render_monthly_pdf, render_weekly_log_pdf
)
from app.services.mail_service import (
    send_invoice_email,
    create_weekly_email_body,
    create_weekly_with_logs_email_body,
    create_monthly_email_body
)
from app.services.folder_service import (
    expand_path,
    ensure_folders,
    weekly_path,
    weekly_log_path,
    monthly_path,
    logs_path,
    write_sidecar
)
from app.services.report_service import report_exception_async
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


def _extract_email_field(payload, field_name):
    """
    Extract an optional email field from the payload.

    Empty / missing values are treated as "no email — skip this recipient".
    Returns the trimmed string on success, or raises ValueError if the
    value is the wrong type. Bare .strip() on payload.get() crashes on
    None / int / dict, which used to bubble up as a 500.

    Returns:
        str: trimmed email, or "" if missing/empty
    Raises:
        ValueError: if the field is present but not a string
    """
    if field_name not in payload:
        return ""
    raw = payload[field_name]
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValueError(f"{field_name} must be a string")
    return raw.strip()


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
        required_fields = ['hours', 'week']
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

        # Validate email addresses (only if provided and non-empty).
        # Skipped entirely when saveOnly=true: no email is being sent in
        # that mode, so a stale typo in clientEmail/accountantEmail would
        # otherwise trap the user on a screen that doesn't expose the
        # field for editing. (Defense in depth — the frontend now omits
        # the email fields from saveOnly payloads anyway.)
        save_only = bool(payload.get('saveOnly'))
        try:
            client_email = _extract_email_field(payload, 'clientEmail')
            accountant_email = _extract_email_field(payload, 'accountantEmail')
        except ValueError as e:
            if save_only:
                # Even wrong-type emails are tolerated in save-only mode —
                # just fall back to "no recipients" since we won't email anyone.
                client_email = ""
                accountant_email = ""
            else:
                return jsonify({
                    "success": False,
                    "error": "Invalid email",
                    "message": str(e)
                }), 400

        if not save_only:
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
            template_id = config.get('template', 'morning-light')
            pdf_bytes = render_weekly_pdf(
                config=config,
                hours=payload['hours'],
                week=week,
                template_id=template_id
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
                "template": config.get('template', 'morning-light')
            }
            write_sidecar(pdf_path, sidecar_data)
        except Exception as e:
            # Non-critical error - log but continue
            logger.warning("Failed to write sidecar JSON: %s", e)

        # If saveOnly, skip email and return immediately
        if payload.get('saveOnly'):
            return jsonify({
                "success": True,
                "saved": pdf_path,
                "sent": [],
                "overwrite": overwrite
            }), 200

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
        report_exception_async(e)
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
        try:
            accountant_email = _extract_email_field(payload, 'accountantEmail')
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid email",
                "message": str(e)
            }), 400

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

        # Signature font and date (optional)
        signature_font = ''
        raw_font = payload.get('signatureFont', '')
        if isinstance(raw_font, str) and raw_font.strip():
            signature_font = raw_font.strip()

        sign_date = datetime.now().strftime('%B %d, %Y')

        # Generate PDF
        try:
            template_id = config.get('template', 'morning-light')
            pdf_bytes = render_monthly_pdf(
                config=config,
                week_data=payload['weekData'],
                month_label=month_label,
                template_id=template_id,
                signature_font=signature_font,
                sign_date=sign_date,
                mileage=payload.get('mileage', 0)
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
        report_exception_async(e)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500


def _load_daily_logs_for_week(save_folder, monday_str):
    """
    Load daily logs for a given week.

    Always includes Mon-Fri (with has_data=False placeholders for missing days).
    Saturday and Sunday are included only when a daily log file exists for them,
    so weekday-only weeks don't get empty weekend sections in the PDF.
    """
    from app.api.config_api import get_config_path, get_or_create_config
    config_path = get_config_path()
    get_or_create_config(config_path)
    config = load_config()

    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    monday = datetime.strptime(monday_str, '%Y%m%d')
    daily_logs = []

    # Get active client info
    clients = config.get('clients', [])
    active_id = config.get('activeClientId', '')
    client = None
    for c in clients:
        if c.get('id') == active_id:
            client = c
            break
    if not client and clients:
        client = clients[0]
    client = client or {'name': '', 'address': '', 'objective': ''}
    if 'objective' not in client:
        client['objective'] = ''

    for i, day_name in enumerate(day_names):
        date = monday + timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        date_label = date.strftime('%A, %B ') + str(date.day) + date.strftime(', %Y')

        try:
            path = logs_path(save_folder, date_str)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Use client snapshot from daily log if available (overrides config)
            log_client = data.get('client')
            if log_client and isinstance(log_client, dict):
                for field in ('name', 'address', 'objective'):
                    if log_client.get(field) and not client.get(field):
                        client[field] = log_client[field]

            daily_logs.append({
                'date_label': date_label,
                'shift': data.get('shift', {}),
                'vitals': data.get('vitals', {}),
                'meds': data.get('meds', []),
                'sections': data.get('sections', []),
                'has_data': True,
            })
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            daily_logs.append({
                'date_label': date_label,
                'shift': {}, 'vitals': {}, 'meds': [], 'sections': [],
                'has_data': False,
            })

    # Trim trailing weekend days that have no data; keep Mon-Fri always.
    while len(daily_logs) > 5 and not daily_logs[-1]['has_data']:
        daily_logs.pop()

    return daily_logs, client


@submit_bp.route('/preview-weekly-log', methods=['POST'])
@limiter.limit(SUBMIT_RATE_LIMIT)
def preview_weekly_log():
    """
    POST /api/submit/preview-weekly-log

    Generates a weekly service log PDF preview (without saving).
    Returns PDF bytes as application/pdf.

    Expects JSON: {"invNum": "INV-20260324"}
    """
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Invalid JSON"}), 400

        inv_num = payload.get('invNum', '')
        if not inv_num or not re.match(r'^INV-\d{8}$', inv_num):
            return jsonify({"error": "Invalid invoice number"}), 400

        # Load config (coerces rate to float)
        from app.api.config_api import get_config_path, get_or_create_config
        config_path = get_config_path()
        get_or_create_config(config_path)
        config = load_config()

        save_folder = expand_path(config.get('saveFolder', ''))
        if not save_folder:
            return jsonify({"error": "No save folder configured"}), 400

        monday_str = inv_num.replace('INV-', '')
        daily_logs, client = _load_daily_logs_for_week(save_folder, monday_str)

        # Compute week label
        monday = datetime.strptime(monday_str, '%Y%m%d')
        end_day = monday + timedelta(days=max(len(daily_logs) - 1, 4))
        week_label = (f"{monday.strftime('%B')} {monday.day} – "
                      f"{end_day.strftime('%B')} {end_day.day}, {end_day.year}")

        signature_font = config.get('signatureFont', '')
        sign_date = datetime.now().strftime('%B ') + str(datetime.now().day) + datetime.now().strftime(', %Y')

        template_id = config.get('template', 'morning-light')
        pdf_bytes = render_weekly_log_pdf(
            config=config, client=client, daily_logs=daily_logs,
            week_label=week_label, template_id=template_id,
            signature_font=signature_font, sign_date=sign_date
        )

        from flask import Response
        return Response(pdf_bytes, mimetype='application/pdf')

    except ValueError as e:
        return jsonify({"error": f"Invalid template or config: {e}"}), 400
    except Exception as e:
        logger.exception("Error generating log preview: %s", e)
        report_exception_async(e)
        return jsonify({"error": str(e)}), 500


@submit_bp.route('/weekly-with-logs', methods=['POST'])
@limiter.limit(SUBMIT_RATE_LIMIT)
def submit_weekly_with_logs():
    """
    POST /api/submit/weekly-with-logs

    Generates the weekly log PDF, saves it, reads the already-saved invoice PDF,
    and emails both as attachments.

    Expects JSON: {
        "invNum": "INV-20260324",
        "clientEmail": "...",
        "accountantEmail": "...",
        "hours": {"Monday": 8, ...}  (for email body totals)
    }
    """
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Invalid JSON"}), 400

        inv_num = payload.get('invNum', '')
        if not inv_num or not re.match(r'^INV-\d{8}$', inv_num):
            return jsonify({"error": "Invalid invoice number"}), 400

        # Load config (coerces rate to float)
        from app.api.config_api import get_config_path, get_or_create_config
        config_path = get_config_path()
        get_or_create_config(config_path)
        config = load_config()

        save_folder = expand_path(config.get('saveFolder', ''))
        if not save_folder:
            return jsonify({"error": "No save folder configured"}), 400

        ensure_folders(save_folder)

        # Read the already-saved invoice PDF
        invoice_pdf_path = weekly_path(save_folder, inv_num)
        if not os.path.exists(invoice_pdf_path):
            return jsonify({"error": "Invoice PDF not found. Save the invoice first."}), 400

        with open(invoice_pdf_path, 'rb') as f:
            invoice_pdf_bytes = f.read()

        # Generate weekly log PDF
        monday_str = inv_num.replace('INV-', '')
        daily_logs, client = _load_daily_logs_for_week(save_folder, monday_str)

        monday = datetime.strptime(monday_str, '%Y%m%d')
        end_day = monday + timedelta(days=max(len(daily_logs) - 1, 4))
        week_label = (f"{monday.strftime('%B')} {monday.day} – "
                      f"{end_day.strftime('%B')} {end_day.day}, {end_day.year}")

        signature_font = config.get('signatureFont', '')
        sign_date = datetime.now().strftime('%B ') + str(datetime.now().day) + datetime.now().strftime(', %Y')

        template_id = config.get('template', 'morning-light')
        log_pdf_bytes = render_weekly_log_pdf(
            config=config, client=client, daily_logs=daily_logs,
            week_label=week_label, template_id=template_id,
            signature_font=signature_font, sign_date=sign_date
        )

        # Save log PDF
        log_pdf_path = weekly_log_path(save_folder, inv_num)
        with open(log_pdf_path, 'wb') as f:
            f.write(log_pdf_bytes)

        # Email both PDFs
        client_email = (payload.get('clientEmail') or '').strip()
        accountant_email = (payload.get('accountantEmail') or '').strip()
        recipients = [e for e in [client_email, accountant_email] if e]

        email_error = None
        if recipients:
            hours = payload.get('hours', {})
            total_hours = sum(hours.values()) if hours else 0
            total_pay = total_hours * config.get('rate', 0)

            # Compute date range for email subject
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            worked_days = [i for i, day in enumerate(day_order) if hours.get(day, 0) > 0]
            if worked_days:
                first_worked = monday + timedelta(days=worked_days[0])
                last_worked = monday + timedelta(days=worked_days[-1])
                work_start = f"{first_worked.strftime('%B')} {first_worked.day}"
                work_end = f"{last_worked.strftime('%B')} {last_worked.day}, {last_worked.year}"
            else:
                work_start = monday.strftime('%B ') + str(monday.day)
                work_end = friday.strftime('%B ') + str(friday.day) + friday.strftime(', %Y')

            email_subject = f"Invoice & Service Log {inv_num} - {work_start} to {work_end}"
            email_body = create_weekly_with_logs_email_body(
                name=config.get('name', 'Provider'),
                week_start=work_start, week_end=work_end,
                total_hours=total_hours, total_pay=total_pay
            )

            try:
                email_result = send_invoice_email(
                    recipients=recipients,
                    subject=email_subject,
                    body=email_body,
                    attachments=[
                        {"bytes": invoice_pdf_bytes, "filename": f"{inv_num}.pdf"},
                        {"bytes": log_pdf_bytes, "filename": f"{inv_num}-LOG.pdf"},
                    ]
                )
            except Exception as e:
                logger.exception("Email sending failed: %s", e)
                email_result = {'success': False, 'error': str(e)}

            if not email_result.get('success'):
                email_error = email_result.get('error', 'Unknown email error')

        response = {
            "success": True,
            "savedInvoice": invoice_pdf_path,
            "savedLog": log_pdf_path,
            "sent": recipients if not email_error else [],
        }
        if email_error:
            response["emailError"] = email_error

        return jsonify(response), 200

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": f"Invalid template or config: {e}",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.exception("Unexpected error in submit_weekly_with_logs: %s", e)
        report_exception_async(e)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500
