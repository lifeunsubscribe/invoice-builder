"""
Report Service

Collects diagnostic data (logs, config, system info) and sends
problem/crash reports to the developer via Gmail SMTP.

Reports go to: lifeunsubscribe+invoice-builder@gmail.com

If SMTP fails (offline, missing creds, throttled), the report is
spooled to a local pending-queue directory so a later launch can
retry. Without the spool, an offline crash silently disappears.
"""

import json
import logging
import os
import platform
import sys
import tempfile
import traceback
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

REPORT_EMAIL = "lifeunsubscribe+invoice-builder@gmail.com"
SMS_GATEWAY = "9544946804@tmomail.net"

# Directory for reports that couldn't be sent (no network, bad creds, etc.).
# Drained on every successful send_report() call.
PENDING_REPORTS_DIR = os.path.join(
    tempfile.gettempdir(), 'invoice-builder-pending-reports'
)


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


def report_exception_async(exc):
    """
    Fire-and-forget crash report for an exception. Never raises, never blocks.

    Use this from route handlers that catch their own exceptions and return
    a custom 500 response — Flask's @errorhandler(500) does NOT fire in that
    case, so the crash would otherwise be silent.
    """
    try:
        import threading
        import traceback as tb
        err_info = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb.format_exc(),
        }
        threading.Thread(
            target=send_report, kwargs={"error_info": err_info}, daemon=True
        ).start()
    except Exception:
        pass  # Crash reporting must never break the response path


def _spool_pending_report(report, sms_text=None):
    """Persist a report to disk so a future launch can retry sending it."""
    try:
        os.makedirs(PENDING_REPORTS_DIR, exist_ok=True)
        fname = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
        fpath = os.path.join(PENDING_REPORTS_DIR, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    "subject": report["subject"],
                    "body": report["body"],
                    "sms_text": sms_text,
                    "spooled_at": datetime.now().isoformat(),
                },
                f,
            )
        logger.info("Report spooled to %s for later retry", fpath)
        return fpath
    except Exception as e:
        logger.warning("Failed to spool pending report: %s", e)
        return None


def _send_one_email(gmail_address, gmail_password, to_addr, subject, body, smtp_host, smtp_port):
    """Send a single MIMEText email. Returns True on success, raises on failure."""
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = gmail_address
    msg['To'] = to_addr
    msg['Subject'] = subject

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, [to_addr], msg.as_string())
    return True


def _drain_pending_reports():
    """
    Try to send any reports that were spooled while offline.

    Called from send_report() after a successful live send. Each spooled
    file is sent and deleted; failures stay on disk for the next attempt.
    Best-effort — never raises.
    """
    if not os.path.isdir(PENDING_REPORTS_DIR):
        return
    try:
        from app.services.mail_service import _get_smtp_credentials, SMTP_HOST, SMTP_PORT
        gmail_address, gmail_password = _get_smtp_credentials()
    except Exception as e:
        logger.warning("Cannot drain pending reports — credentials unavailable: %s", e)
        return

    sent_count = 0
    for fname in sorted(os.listdir(PENDING_REPORTS_DIR)):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(PENDING_REPORTS_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                spooled = json.load(f)
            subject = "[RETRY] " + spooled.get("subject", "Invoice Builder report")
            body = (
                f"(Originally spooled at {spooled.get('spooled_at', 'unknown')})\n\n"
                + spooled.get("body", "")
            )
            _send_one_email(
                gmail_address, gmail_password, REPORT_EMAIL,
                subject, body, SMTP_HOST, SMTP_PORT
            )
            os.remove(fpath)
            sent_count += 1
        except Exception as e:
            logger.warning("Failed to drain spooled report %s: %s", fname, e)
            # Leave on disk; next launch can try again.
            break
    if sent_count:
        logger.info("Drained %d pending crash report(s)", sent_count)


def send_report(user_description="", error_info=None):
    """
    Collect diagnostics and send the report email + SMS notification.

    Returns:
        dict: {"success": True} or {"success": False, "error": "...", "report": "..."}
        When email fails, the report is also spooled to PENDING_REPORTS_DIR
        for retry on a future launch, AND 'report' contains the full text
        so the frontend can offer a clipboard fallback.
    """
    report = collect_report(user_description, error_info)
    sms_text = _build_sms_text(user_description, error_info)

    # Try to send via existing Gmail SMTP credentials
    try:
        from app.services.mail_service import _get_smtp_credentials, SMTP_HOST, SMTP_PORT

        gmail_address, gmail_password = _get_smtp_credentials()

        _send_one_email(
            gmail_address, gmail_password, REPORT_EMAIL,
            report["subject"], report["body"], SMTP_HOST, SMTP_PORT
        )
        logger.info("Report sent successfully: %s", report["subject"])

        # Send SMS notification (best-effort, don't fail the report)
        try:
            _send_one_email(
                gmail_address, gmail_password, SMS_GATEWAY,
                "", sms_text, SMTP_HOST, SMTP_PORT
            )
            logger.info("SMS notification sent")
        except Exception as e:
            logger.warning("SMS notification failed (non-critical): %s", e)

        # Live send worked — opportunistically drain anything that was
        # spooled while we were offline.
        try:
            _drain_pending_reports()
        except Exception as e:
            logger.warning("Drain pass failed (non-critical): %s", e)

        return {"success": True}

    except Exception as e:
        logger.warning("Failed to send report email: %s", e)
        # Spool to disk so a later launch can retry. Without this, an
        # offline crash silently disappears.
        _spool_pending_report(report, sms_text=sms_text)
        return {
            "success": False,
            "error": str(e),
            "report": f"{report['subject']}\n\n{report['body']}",
        }
