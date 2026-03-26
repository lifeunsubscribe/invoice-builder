"""
PDF Generation Service

Renders HTML invoice templates to PDF using WeasyPrint.
Supports three weekly invoice templates (morning-light, caring-hands, garden)
and one monthly report template.

Functions:
    render_weekly_pdf(config, hours, week, template_id) -> bytes
    render_monthly_pdf(config, week_data, month_label) -> bytes
"""

import os
from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML


# Template directory (relative to this file)
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')

# Template ID to filename mapping
WEEKLY_TEMPLATES = {
    'morning-light': 'invoice_morning_light.html',
    'caring-hands': 'invoice_caring_hands.html',
    'garden': 'invoice_garden.html'
}


def _get_jinja_env():
    """Initialize and return Jinja2 environment for template rendering."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(['html', 'xml'])
    )


def _calculate_weekly_totals(hours, rate):
    """
    Calculate total hours and total pay from hours dictionary.

    Args:
        hours: dict mapping day names to hour counts (e.g., {'Monday': 8, ...})
        rate: float, hourly rate

    Returns:
        tuple of (total_hours: int, total_pay: str)
    """
    total_hours = sum(hours.values())
    total_pay = total_hours * rate
    return total_hours, f"{total_pay:.2f}"


def _calculate_monthly_totals(week_data, rate):
    """
    Calculate monthly totals from week data.

    Args:
        week_data: list of dicts with 'hours' keys
        rate: float, hourly rate

    Returns:
        tuple of (total_hours: int, total_pay: str, weeks_worked: int)
    """
    total_hours = sum(week.get('hours', 0) for week in week_data)
    total_pay = total_hours * rate
    weeks_worked = sum(1 for week in week_data if week.get('hours', 0) > 0)
    return total_hours, f"{total_pay:.2f}", weeks_worked


def render_weekly_pdf(config, hours, week, template_id):
    """
    Render a weekly invoice PDF from template data.

    Args:
        config: dict with user/client configuration
            - name: str, provider name
            - address: str, provider address
            - personalEmail: str, provider email
            - rate: float, hourly rate
            - clientName: str, client agency name
            - clientEmail: str, client billing email
            - invoiceNote: str, footer note text
        hours: dict mapping day names to hour counts
            - {'Monday': 8, 'Tuesday': 8, ...}
        week: dict with week metadata
            - start: str, week start date (e.g., "March 24")
            - end: str, week end date (e.g., "March 30, 2026")
            - invNum: str, invoice number (e.g., "INV-20260324")
            - dayDates: dict mapping day names to short dates (e.g., {'Monday': 'Mar 24'})
        template_id: str, template variant identifier
            - 'morning-light', 'caring-hands', or 'garden'

    Returns:
        bytes: PDF file contents

    Raises:
        ValueError: if template_id is invalid
        FileNotFoundError: if template file is missing
        RuntimeError: if PDF rendering fails
    """
    # Validate template ID
    if template_id not in WEEKLY_TEMPLATES:
        raise ValueError(
            f"Invalid template_id '{template_id}'. "
            f"Must be one of: {', '.join(WEEKLY_TEMPLATES.keys())}"
        )

    # Calculate totals
    total_hours, total_pay = _calculate_weekly_totals(hours, config['rate'])

    # Prepare template context
    context = {
        'config': config,
        'hours': hours,
        'week': week,
        'total_hours': total_hours,
        'total_pay': total_pay
    }

    # Load and render template
    try:
        env = _get_jinja_env()
        template_filename = WEEKLY_TEMPLATES[template_id]
        template = env.get_template(template_filename)
        html_content = template.render(**context)
    except Exception as e:
        raise FileNotFoundError(
            f"Failed to load template '{template_id}': {str(e)}"
        ) from e

    # Render PDF
    try:
        pdf_bytes_io = BytesIO()
        HTML(string=html_content, base_url=TEMPLATE_DIR).write_pdf(pdf_bytes_io)
        return pdf_bytes_io.getvalue()
    except Exception as e:
        raise RuntimeError(
            f"Failed to render PDF for template '{template_id}': {str(e)}"
        ) from e


def render_monthly_pdf(config, week_data, month_label):
    """
    Render a monthly hours summary PDF.

    Args:
        config: dict with user/client configuration
            - name: str, provider name
            - address: str, provider address
            - personalEmail: str, provider email
            - rate: float, hourly rate
            - clientName: str, client agency name
            - clientEmail: str, client billing email
            - accountantEmail: str, accountant email
        week_data: list of dicts with week information
            - Each dict: {'label': str (e.g., "Mar 3 – Mar 9"), 'hours': int}
        month_label: str, month and year (e.g., "March 2026")

    Returns:
        bytes: PDF file contents

    Raises:
        FileNotFoundError: if template file is missing
        RuntimeError: if PDF rendering fails
    """
    # Calculate totals
    total_hours, total_pay, weeks_worked = _calculate_monthly_totals(
        week_data, config['rate']
    )

    # Prepare template context
    context = {
        'config': config,
        'week_data': week_data,
        'month_label': month_label,
        'total_hours': total_hours,
        'total_pay': total_pay,
        'weeks_worked': weeks_worked
    }

    # Load and render template
    try:
        env = _get_jinja_env()
        template = env.get_template('invoice_monthly.html')
        html_content = template.render(**context)
    except Exception as e:
        raise FileNotFoundError(
            f"Failed to load monthly template: {str(e)}"
        ) from e

    # Render PDF
    try:
        pdf_bytes_io = BytesIO()
        HTML(string=html_content, base_url=TEMPLATE_DIR).write_pdf(pdf_bytes_io)
        return pdf_bytes_io.getvalue()
    except Exception as e:
        raise RuntimeError(
            f"Failed to render monthly PDF: {str(e)}"
        ) from e
