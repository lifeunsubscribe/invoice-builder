"""
Report Service

Collects diagnostic data (logs, config, system info) and sends
problem/crash reports to the developer via Gmail SMTP.

Reports go to: lifeunsubscribe+invoice-builder@gmail.com
"""

import json
import logging
import os
import platform
import sys
import tempfile
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

REPORT_EMAIL = "lifeunsubscribe+invoice-builder@gmail.com"
SMS_GATEWAY = "9544946804@tmomail.net"


def _get_app_version():
    """Read the baked-in build version."""
    if getattr(sys, 'frozen', False):
        ver_path = os.path.join(sys._MEIPASS, 'app', 'build_version.txt')
    else:
        ver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build_version.txt')
    try:
        with open(ver_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "dev"


def _get_log_tail(max_lines=200):
    """Read the last N lines of the app log file."""
    if not getattr(sys, 'frozen', False):
        return "(dev mode — logs go to console)"
    log_path = os.path.join(tempfile.gettempdir(), 'invoice_builder.log')
    try:
        with open(log_path, 'r', errors='replace') as f:
            lines = f.readlines()
        return ''.join(lines[-max_lines:])
    except FileNotFoundError:
        return "(no log file found)"
    except Exception as e:
        return f"(error reading log: {e})"


def _get_sanitized_config():
    """Load config.json with sensitive fields redacted."""
    from app.api.config_api import get_config_path
    config_path = get_config_path()
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        # Redact email addresses (keep domain for debugging)
        for key in ('personalEmail', 'clientEmail', 'accountantEmail'):
            val = config.get(key, '')
            if '@' in val:
                config[key] = f"***@{val.split('@')[1]}"
        return json.dumps(config, indent=2)
    except Exception as e:
        return f"(error reading config: {e})"


def _get_system_info():
    """Collect system/environment info for debugging."""
    return {
        "app_version": _get_app_version(),
        "frozen": getattr(sys, 'frozen', False),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "timestamp": datetime.now().isoformat(),
    }


def collect_report(user_description="", error_info=None):
    """
    Build the full diagnostic report payload.

    Args:
        user_description: Optional user-written description of the problem
        error_info: Optional dict with 'type', 'message', 'traceback' for crashes

    Returns:
        dict with 'subject' and 'body' ready for emailing
    """
    sys_info = _get_system_info()
    is_crash = error_info is not None

    subject = (
        f"[CRASH] Invoice Builder v{sys_info['app_version']} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        if is_crash else
        f"[Report] Invoice Builder v{sys_info['app_version']} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    sections = []

    if user_description:
        sections.append(f"=== USER DESCRIPTION ===\n{user_description}")

    if is_crash:
        sections.append(
            f"=== CRASH INFO ===\n"
            f"Type: {error_info.get('type', 'Unknown')}\n"
            f"Message: {error_info.get('message', 'Unknown')}\n"
            f"Traceback:\n{error_info.get('traceback', 'N/A')}"
        )

    sections.append(
        f"=== SYSTEM INFO ===\n"
        + '\n'.join(f"{k}: {v}" for k, v in sys_info.items())
    )

    sections.append(f"=== CONFIG (sanitized) ===\n{_get_sanitized_config()}")
    sections.append(f"=== RECENT LOGS (last 200 lines) ===\n{_get_log_tail()}")

    return {"subject": subject, "body": '\n\n'.join(sections)}


def _build_sms_text(user_description="", error_info=None):
    """Build a short SMS-friendly summary (≤160 chars)."""
    if error_info:
        err_type = error_info.get('type', 'Error')
        err_msg = error_info.get('message', '')
        detail = f"{err_type}: {err_msg}"
    elif user_description:
        detail = user_description
    else:
        detail = "No details"
    prefix = "Invoice Builder CRASH: " if error_info else "Invoice Builder feedback: "
    suffix = " — check email."
    max_detail = 160 - len(prefix) - len(suffix)
    if len(detail) > max_detail:
        detail = detail[:max_detail - 1] + "…"
    return f"{prefix}{detail}{suffix}"


def send_report(user_description="", error_info=None):
    """
    Collect diagnostics and send the report email + SMS notification.

    Returns:
        dict: {"success": True} or {"success": False, "error": "...", "report": "..."}
        When email fails, 'report' contains the full text so the frontend
        can offer a clipboard fallback.
    """
    report = collect_report(user_description, error_info)

    # Try to send via existing Gmail SMTP credentials
    try:
        from app.services.mail_service import _get_smtp_credentials, SMTP_HOST, SMTP_PORT
        import smtplib
        from email.mime.text import MIMEText

        gmail_address, gmail_password = _get_smtp_credentials()

        # Send full report email
        msg = MIMEText(report["body"], 'plain', 'utf-8')
        msg['From'] = gmail_address
        msg['To'] = REPORT_EMAIL
        msg['Subject'] = report["subject"]

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, [REPORT_EMAIL], msg.as_string())

        logger.info("Report sent successfully: %s", report["subject"])

        # Send SMS notification (best-effort, don't fail the report)
        try:
            sms_text = _build_sms_text(user_description, error_info)
            sms = MIMEText(sms_text, 'plain', 'utf-8')
            sms['From'] = gmail_address
            sms['To'] = SMS_GATEWAY
            sms['Subject'] = ""  # carriers ignore subject; keep empty

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(gmail_address, gmail_password)
                server.sendmail(gmail_address, [SMS_GATEWAY], sms.as_string())
            logger.info("SMS notification sent")
        except Exception as e:
            logger.warning("SMS notification failed (non-critical): %s", e)

        return {"success": True}

    except Exception as e:
        logger.warning("Failed to send report email: %s", e)
        return {
            "success": False,
            "error": str(e),
            "report": f"{report['subject']}\n\n{report['body']}"
        }
