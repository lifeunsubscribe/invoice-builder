"""
PDF Generation Service

Renders HTML invoice templates to PDF using WeasyPrint.
Template registry is driven by app/themes.py — add new themes there,
not here. This module reads WEEKLY_TEMPLATE_FILES, MONTHLY_TEMPLATE_FILES,
and LOG_TEMPLATE_FILES from themes.py automatically.

Functions:
    render_weekly_pdf(config, hours, week, template_id)  -> bytes
    render_monthly_pdf(config, week_data, month_label, ...) -> bytes
    render_weekly_log_pdf(config, client, daily_logs, ...) -> bytes
"""

import os
from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.themes import (
    WEEKLY_TEMPLATE_FILES,
    MONTHLY_TEMPLATE_FILES,
    LOG_TEMPLATE_FILES,
    THEME_ORDER,
    get_theme,
)

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_jinja_env():
    """Initialize and return a Jinja2 environment pointing at app/templates/."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(['html', 'xml'])
    )


def _validate_config(config, required_keys):
    """
    Raise ValueError listing any required keys missing from config.

    Args:
        config: dict
        required_keys: list[str]
    Raises:
        ValueError
    """
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")


def _validate_template_id(template_id, template_map):
    """
    Raise ValueError if template_id is not in the given mapping.

    Args:
        template_id: str
        template_map: dict mapping template_id -> filename
    Raises:
        ValueError
    """
    if template_id not in template_map:
        raise ValueError(
            f"Invalid template_id '{template_id}'. "
            f"Must be one of: {', '.join(THEME_ORDER)}"
        )


def _coerce_rate(rate):
    """Coerce rate to float, defaulting to 0.0 on bad input.

    Defensive: rate is sometimes saved as a string from form input.
    """
    try:
        return float(rate)
    except (TypeError, ValueError):
        return 0.0


def _calculate_weekly_totals(hours, rate):
    """
    Return (total_hours: int, total_pay: str) for a weekly hours dict.

    Args:
        hours: dict mapping day name -> hour count
        rate: float (or string-like that can be coerced)
    Returns:
        tuple[int, str]
    """
    total_hours = sum(hours.values())
    return total_hours, f"{total_hours * _coerce_rate(rate):.2f}"


def _calculate_monthly_totals(week_data, rate):
    """
    Return (total_hours, total_pay, weeks_worked) for a list of week dicts.

    Args:
        week_data: list of dicts with 'hours' key
        rate: float (or string-like that can be coerced)
    Returns:
        tuple[int, str, int]
    """
    total_hours = sum(w.get('hours', 0) for w in week_data)
    weeks_worked = sum(1 for w in week_data if w.get('hours', 0) > 0)
    return total_hours, f"{total_hours * _coerce_rate(rate):.2f}", weeks_worked


def _render_to_pdf(html_content):
    """
    Render an HTML string to PDF bytes via WeasyPrint.

    Args:
        html_content: str
    Returns:
        bytes
    Raises:
        OSError, RuntimeError
    """
    try:
        buf = BytesIO()
        HTML(string=html_content, base_url=TEMPLATE_DIR).write_pdf(buf)
        return buf.getvalue()
    except OSError as e:
        raise OSError(f"I/O error rendering PDF: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to render PDF: {e}") from e


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_weekly_pdf(config, hours, week, template_id):
    """
    Render a weekly invoice PDF.

    Args:
        config: dict — must include: name, address, personalEmail, rate,
                clientName, clientEmail, invoiceNote.
        hours: dict — day name -> hour count (e.g. {'Monday': 8, ...})
        week: dict — start, end, invNum, dayDates
        template_id: str — must be a key in THEME_ORDER

    Returns:
        bytes — PDF content

    Raises:
        ValueError — bad template_id or missing config keys
        FileNotFoundError — template file missing
        RuntimeError — rendering failure
    """
    _validate_template_id(template_id, WEEKLY_TEMPLATE_FILES)
    _validate_config(config, [
        'name', 'address', 'personalEmail', 'rate',
        'clientName', 'clientEmail', 'invoiceNote',
    ])

    total_hours, total_pay = _calculate_weekly_totals(hours, config['rate'])

    # Occupation-specific invoice title
    occ_titles = {
        'home-health-aide': 'Home Health Invoice',
        'personal-care': 'Personal Care Invoice',
    }
    invoice_title = occ_titles.get(config.get('occupation', ''), 'Contractor Invoice')

    context = {
        'config': config,
        'hours': hours,
        'week': week,
        'total_hours': total_hours,
        'total_pay': total_pay,
        'invoice_title': invoice_title,
    }

    try:
        env = _get_jinja_env()
        tmpl = env.get_template(WEEKLY_TEMPLATE_FILES[template_id])
        html_content = tmpl.render(**context)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Template file not found for '{template_id}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to render template '{template_id}': {e}"
        ) from e

    return _render_to_pdf(html_content)


def render_monthly_pdf(config, week_data, month_label,
                       template_id='caring-hands',
                       signature_font='', sign_date='',
                       mileage=0):
    """
    Render a monthly hours summary PDF.

    Args:
        config: dict — must include: name, address, personalEmail, rate,
                clientName, clientEmail, accountantEmail.
        week_data: list of dicts — each with 'label' (str) and 'hours' (int)
        month_label: str — e.g. "March 2026"
        template_id: str — theme to use (default 'caring-hands')
        signature_font: str — Google Font name for cursive signature
        sign_date: str — date string for signature line

    Returns:
        bytes — PDF content

    Raises:
        ValueError — missing config keys or bad template_id
        FileNotFoundError — template file missing
        RuntimeError — rendering failure
    """
    _validate_template_id(template_id, MONTHLY_TEMPLATE_FILES)
    _validate_config(config, [
        'name', 'address', 'personalEmail', 'rate',
        'clientName', 'clientEmail', 'accountantEmail',
    ])

    total_hours, total_pay, weeks_worked = _calculate_monthly_totals(
        week_data, config['rate']
    )

    context = {
        'config': config,
        'week_data': week_data,
        'month_label': month_label,
        'total_hours': total_hours,
        'total_pay': total_pay,
        'weeks_worked': weeks_worked,
        'signature_font': signature_font,
        'sign_date': sign_date,
        'mileage': mileage,
    }

    try:
        env = _get_jinja_env()
        tmpl = env.get_template(MONTHLY_TEMPLATE_FILES[template_id])
        html_content = tmpl.render(**context)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Monthly template file not found for '{template_id}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to render monthly template '{template_id}': {e}"
        ) from e

    return _render_to_pdf(html_content)


def render_weekly_log_pdf(config, client, daily_logs, week_label,
                          template_id='morning-light',
                          signature_font='', sign_date=''):
    """
    Render a consolidated weekly service log PDF (Mon-Fri).

    Args:
        config: dict with provider info (name, address, personalEmail)
        client: dict with patient info (name, address, objective)
        daily_logs: list of 5 dicts (Mon-Fri), each with:
            - date_label: str ("Monday, March 24, 2026")
            - shift: dict with start/end or empty dict
            - vitals: dict or empty dict
            - meds: list of med dicts or empty list
            - sections: list of section dicts or empty list
            - has_data: bool
        week_label: str (e.g., "March 24 – March 28, 2026")
        template_id: str — theme to use (default 'morning-light')
        signature_font: str, Google Font name
        sign_date: str, date for signature line

    Returns:
        bytes: PDF file contents
    """
    _validate_template_id(template_id, LOG_TEMPLATE_FILES)

    # Enrich daily_logs with computed fields
    for day in daily_logs:
        # Compute shift hours
        shift = day.get('shift', {})
        if shift.get('start') and shift.get('end'):
            try:
                sh, sm = map(int, shift['start'].split(':'))
                eh, em = map(int, shift['end'].split(':'))
                diff = (eh * 60 + em) - (sh * 60 + sm)
                day['shift_hours'] = f"{max(0, diff) / 60:.1f}"
            except (ValueError, TypeError):
                day['shift_hours'] = None
        else:
            day['shift_hours'] = None

        # Check if vitals have any non-null values
        vitals = day.get('vitals', {})
        day['has_vitals'] = any(v is not None for v in vitals.values())

    context = {
        'config': config,
        'client': client,
        'daily_logs': daily_logs,
        'week_label': week_label,
        'signature_font': signature_font,
        'sign_date': sign_date,
    }

    try:
        env = _get_jinja_env()
        tmpl = env.get_template(LOG_TEMPLATE_FILES[template_id])
        html_content = tmpl.render(**context)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Log template file not found for '{template_id}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to render log template '{template_id}': {e}"
        ) from e

    return _render_to_pdf(html_content)
