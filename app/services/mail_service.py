"""
Email Service

Sends invoice PDFs via Gmail SMTP with graceful error handling.
Credentials loaded from .env file using python-dotenv.

Functions:
    send_invoice_email(recipients, pdf_bytes, filename, subject, body) -> dict
    create_weekly_email_body(name, week_start, week_end, total_hours, total_pay) -> str
    create_monthly_email_body(name, month_label, total_hours, total_pay) -> str
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from dotenv import load_dotenv


# Gmail SMTP settings
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Load environment variables from .env file
load_dotenv()


def _get_smtp_credentials():
    """
    Load SMTP credentials from environment variables.

    Returns:
        tuple of (gmail_address: str, gmail_password: str)

    Raises:
        ValueError: if GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in .env
    """
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


def send_invoice_email(recipients, pdf_bytes, filename, subject, body):
    """
    Send an email with PDF invoice attachment via Gmail SMTP.

    Args:
        recipients: list of str, recipient email addresses
        pdf_bytes: bytes, PDF file contents to attach
        filename: str, name for the PDF attachment (e.g., "INV-20260324.pdf")
        subject: str, email subject line
        body: str, plain text email body

    Returns:
        dict with success status:
            - {"success": True} if email sent successfully
            - {"success": False, "error": "message"} if sending failed

    Notes:
        - Uses Gmail SMTP (smtp.gmail.com:587) with TLS encryption
        - Credentials loaded from .env via GMAIL_ADDRESS and GMAIL_APP_PASSWORD
        - PDF attached with application/pdf MIME type
        - All errors caught and returned (no exceptions raised)
    """
    # Validate inputs
    if not recipients or len(recipients) == 0:
        return {
            "success": False,
            "error": "No recipients specified"
        }

    if not pdf_bytes:
        return {
            "success": False,
            "error": "No PDF data provided"
        }

    # Load SMTP credentials
    try:
        gmail_address, gmail_password = _get_smtp_credentials()
    except ValueError as e:
        return {
            "success": False,
            "error": str(e)
        }

    # Create email message
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject

        # Attach plain text body
        msg.attach(MIMEText(body, 'plain'))

        # Attach PDF with correct MIME type
        pdf_attachment = MIMEBase('application', 'pdf')
        pdf_attachment.set_payload(pdf_bytes)
        encoders.encode_base64(pdf_attachment)
        pdf_attachment.add_header(
            'Content-Disposition',
            f'attachment; filename={filename}'
        )
        msg.attach(pdf_attachment)

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create email message: {str(e)}"
        }

    # Send email via Gmail SMTP
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()  # Enable TLS encryption
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipients, msg.as_string())
        server.quit()

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
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send email: {str(e)}"
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
