"""
Email Service

Sends invoice PDFs via Gmail SMTP with graceful error handling.
Credentials loaded from .env file using python-dotenv.

Functions:
    send_invoice_email(recipients, pdf_bytes, filename, subject, body) -> dict
    create_weekly_email_body(name, week_start, week_end, total_hours, total_pay) -> str
    create_monthly_email_body(name, month_label, total_hours, total_pay) -> str
"""

import logging
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Gmail SMTP settings
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _get_env_path():
    """Resolve .env file path — lives alongside config.json in the save folder."""
    from app.api.config_api import get_config_path
    config_path = get_config_path()
    return os.path.join(os.path.dirname(config_path), '.env')


# Load environment variables from .env file
load_dotenv(_get_env_path())


def _get_smtp_credentials():
    """
    Load SMTP credentials from environment variables.
    Re-reads .env each time so credential changes take effect without restart.

    Returns:
        tuple of (gmail_address: str, gmail_password: str)

    Raises:
        ValueError: if GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in .env
    """
    # Reload .env so changes (from UI setup or manual edits) take effect immediately
    load_dotenv(_get_env_path(), override=True)

    gmail_address = os.getenv('GMAIL_ADDRESS')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')

    if not gmail_address:
        raise ValueError(
            "GMAIL_ADDRESS not found in .env file. "
            "Please set your Gmail address in .env"
        )

    if not gmail_password:
        raise ValueError(
            "GMAIL_APP_PASSWORD not found in .env file. "
            "Please set your Gmail app password in .env"
        )

    return gmail_address, gmail_password


def send_invoice_email(recipients, pdf_bytes=None, filename=None, subject='',
                       body='', attachments=None):
    """
    Send an email with one or more PDF attachments via Gmail SMTP.

    Args:
        recipients: list of str, recipient email addresses
        pdf_bytes: bytes, PDF file contents (legacy single-attachment mode)
        filename: str, attachment name (legacy single-attachment mode)
        subject: str, email subject line
        body: str, plain text email body
        attachments: list of dicts, each with 'bytes' and 'filename' keys
            (overrides pdf_bytes/filename when provided)

    Returns:
        dict: {"success": True} or {"success": False, "error": "..."}
    """
    # Build attachments list (support both old and new calling conventions)
    if attachments is None:
        if not pdf_bytes:
            return {"success": False, "error": "No PDF data provided"}
        attachments = [{"bytes": pdf_bytes, "filename": filename or "document.pdf"}]

    # Validate inputs
    if not recipients or len(recipients) == 0:
        return {"success": False, "error": "No recipients specified"}

    if not attachments:
        return {"success": False, "error": "No attachments provided"}

    # Load SMTP credentials
    try:
        gmail_address, gmail_password = _get_smtp_credentials()
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Create email message
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject

        # Attach plain text body
        msg.attach(MIMEText(body, 'plain'))

        # Attach all PDFs
        for att in attachments:
            pdf_attachment = MIMEBase('application', 'pdf')
            pdf_attachment.set_payload(att['bytes'])
            encoders.encode_base64(pdf_attachment)
            pdf_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename={att["filename"]}'
            )
            msg.attach(pdf_attachment)

    except UnicodeEncodeError as e:
        logger.exception("Encoding error in email content: %s", e)
        return {
            "success": False,
            "error": f"Encoding error in email content: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create email message: {str(e)}"
        }

    # Send email via Gmail SMTP
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()  # Enable TLS encryption
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, recipients, msg.as_string())

        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "error": "Authentication failed. Please check your Gmail address and app password in .env"
        }
    except smtplib.SMTPException as e:
        return {
            "success": False,
            "error": f"SMTP error occurred: {str(e)}"
        }
    except ConnectionError as e:
        return {
            "success": False,
            "error": f"Connection error: {str(e)}"
        }
    except TimeoutError as e:
        logger.exception("Connection timeout: %s", e)
        return {
            "success": False,
            "error": f"Connection timeout: {str(e)}"
        }
    except Exception as e:
        logger.exception("Unexpected error sending email: %s", e)
        return {
            "success": False,
            "error": f"Unexpected error sending email: {str(e)}"
        }


def create_weekly_email_body(name, week_start, week_end, total_hours, total_pay):
    """
    Generate plain text email body for weekly invoice.

    Args:
        name: str, provider name (e.g., "Lisa Wadley")
        week_start: str, week start date (e.g., "March 24")
        week_end: str, week end date (e.g., "March 30, 2026")
        total_hours: int or float, total hours worked
        total_pay: float, total amount due

    Returns:
        str: Plain text email body matching ADR template format

    Example:
        >>> create_weekly_email_body("Lisa Wadley", "March 24", "March 30, 2026", 40, 1120.00)
        'Hi,\\n\\nPlease find attached my invoice for the week of March 24 – March 30, 2026...
    """
    return f"""Hi,

Please find attached my invoice for the week of {week_start} – {week_end}.

Total hours: {total_hours}
Total due: ${total_pay:.2f}

Thank you,
{name}"""


def create_weekly_with_logs_email_body(name, week_start, week_end, total_hours,
                                       total_pay):
    """Generate email body for weekly invoice + service log attachment."""
    return f"""Hi,

Please find attached my invoice and weekly service log for the week of {week_start} – {week_end}.

Total hours: {total_hours}
Total due: ${total_pay:.2f}

Thank you,
{name}"""


def create_monthly_email_body(name, month_label, total_hours, total_pay):
    """
    Generate plain text email body for monthly report.

    Args:
        name: str, provider name (e.g., "Lisa Wadley")
        month_label: str, month and year (e.g., "March 2026")
        total_hours: int or float, total hours worked in month
        total_pay: float, total invoiced amount for month

    Returns:
        str: Plain text email body matching ADR template format

    Example:
        >>> create_monthly_email_body("Lisa Wadley", "March 2026", 160, 4480.00)
        'Hi,\\n\\nAttached is my monthly hours summary for March 2026...
    """
    return f"""Hi,

Attached is my monthly hours summary for {month_label}.

Total hours: {total_hours}
Total invoiced: ${total_pay:.2f}

Please let me know if you need the individual weekly invoices as well.

Thank you,
{name}"""
