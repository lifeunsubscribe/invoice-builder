"""
Email Config API Blueprint

Handles GET /api/email-status, POST /api/email-config, and POST /api/email-test endpoints.
Checks whether Gmail credentials are configured, allows saving them
to the .env file, and verifies credentials work via SMTP before saving.
"""

import os
import sys
import re
import logging
import smtplib
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

email_config_bp = Blueprint('email_config', __name__, url_prefix='/api')

# Basic email validation pattern
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def _get_env_path():
    """Resolve .env file path for both dev and PyInstaller environments."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.dirname(app_dir)
    return os.path.join(base_dir, '.env')


def _read_env_credentials():
    """
    Read GMAIL_ADDRESS and GMAIL_APP_PASSWORD from the .env file directly.
    Returns (address, password) tuple. Either may be empty string if not set.
    """
    env_path = _get_env_path()
    address = ""
    password = ""

    if not os.path.exists(env_path):
        return address, password

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                if key == 'GMAIL_ADDRESS':
                    address = value
                elif key == 'GMAIL_APP_PASSWORD':
                    password = value
    except Exception as e:
        logger.warning("Could not read .env file: %s", e)

    return address, password


@email_config_bp.route('/email-status', methods=['GET'])
def email_status():
    """
    GET /api/email-status

    Returns whether email credentials are configured.
    Returns the Gmail address (for pre-filling the form) but not the password.
    """
    address, password = _read_env_credentials()

    configured = bool(address) and bool(password)

    return jsonify({
        "configured": configured,
        "hasAddress": bool(address),
        "hasPassword": bool(password),
        "gmailAddress": address if address else "",
    }), 200


@email_config_bp.route('/email-config', methods=['POST'])
def save_email_config():
    """
    POST /api/email-config

    Accepts JSON with gmailAddress and gmailAppPassword.
    Writes them to the .env file and updates os.environ so
    the running process picks up changes immediately.
    """
    try:
        data = request.get_json()
        if data is None:
            return jsonify({
                "error": "Invalid JSON",
                "message": "Request body must be valid JSON"
            }), 400

        gmail_address = data.get('gmailAddress', '').strip()
        gmail_app_password = data.get('gmailAppPassword', '').strip()

        if not gmail_address:
            return jsonify({
                "error": "Missing email",
                "message": "Gmail address is required"
            }), 400

        if not EMAIL_PATTERN.match(gmail_address):
            return jsonify({
                "error": "Invalid email",
                "message": "Please enter a valid Gmail address"
            }), 400

        if not gmail_app_password:
            return jsonify({
                "error": "Missing password",
                "message": "App password is required"
            }), 400

        # Verify credentials work via SMTP before saving
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.starttls()
                server.login(gmail_address, gmail_app_password)
        except smtplib.SMTPAuthenticationError:
            return jsonify({
                "error": "Authentication failed",
                "message": "Gmail rejected these credentials. Double-check your email address and app password. Remember: use an App Password, not your regular Gmail password."
            }), 400
        except smtplib.SMTPException as e:
            logger.warning("SMTP error during credential test: %s", e)
            return jsonify({
                "error": "Connection error",
                "message": f"Could not connect to Gmail: {str(e)}"
            }), 400
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning("Network error during credential test: %s", e)
            return jsonify({
                "error": "Connection error",
                "message": "Could not reach Gmail servers. Check your internet connection and try again."
            }), 400

        # Write to .env file
        env_path = _get_env_path()

        # Read existing .env content to preserve other variables
        existing_lines = []
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()
            except Exception:
                pass

        # Update or add our keys
        found_address = False
        found_password = False
        new_lines = []
        for line in existing_lines:
            stripped = line.strip()
            if stripped.startswith('GMAIL_ADDRESS='):
                new_lines.append(f'GMAIL_ADDRESS={gmail_address}\n')
                found_address = True
            elif stripped.startswith('GMAIL_APP_PASSWORD='):
                new_lines.append(f'GMAIL_APP_PASSWORD={gmail_app_password}\n')
                found_password = True
            else:
                new_lines.append(line)

        if not found_address:
            new_lines.append(f'GMAIL_ADDRESS={gmail_address}\n')
        if not found_password:
            new_lines.append(f'GMAIL_APP_PASSWORD={gmail_app_password}\n')

        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # Update os.environ so the running process picks up changes immediately
        os.environ['GMAIL_ADDRESS'] = gmail_address
        os.environ['GMAIL_APP_PASSWORD'] = gmail_app_password

        return jsonify({
            "success": True,
            "message": "Email credentials saved successfully"
        }), 200

    except PermissionError as e:
        logger.exception("Permission denied writing .env: %s", e)
        return jsonify({
            "error": "Permission denied",
            "message": "Cannot write email configuration file"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error saving email config: %s", e)
        return jsonify({
            "error": "Save failed",
            "message": "An unexpected error occurred while saving email credentials"
        }), 500
