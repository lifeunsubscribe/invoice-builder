"""
PDF Generation Service

Renders invoice PDFs using ReportLab.
Supports three weekly invoice templates (morning-light, caring-hands, garden)
and one monthly report template.

Functions:
    render_weekly_pdf(config, hours, week, template_id) -> bytes
    render_monthly_pdf(config, week_data, month_label) -> bytes
"""

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor


# Page dimensions
PAGE_W, PAGE_H = letter  # 612 x 792 points
MARGIN = 38
RIGHT = PAGE_W - MARGIN

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
        'Saturday', 'Sunday']

# Template ID to filename mapping (kept for backwards compat)
WEEKLY_TEMPLATES = {
    'morning-light': 'invoice_morning_light.html',
    'caring-hands': 'invoice_caring_hands.html',
    'garden': 'invoice_garden.html'
}

# Column positions for weekly invoice table
COL_DAY = MARGIN
COL_HOURS = 340
COL_RATE = 430
COL_AMOUNT = RIGHT

# Column positions for monthly report table
MCOL_WEEK = MARGIN
MCOL_PERIOD = MARGIN + 70
MCOL_HOURS = 370
MCOL_RATE = 440
MCOL_AMOUNT = RIGHT


# ── Theme definitions ──────────────────────────────────────────────────

THEMES = {
    'morning-light': dict(
        accent='#b76e79', dark='#2c1810', med='#6a4a40', light='#9a8070',
        page_bg=None,  # white
        header_bg='#f0d8dc', header_border='#b76e79',
        name_font='Times-Bold', name_color='#2c1810',
        detail_color='#6a4a40',
        inv_num_color='#2c1810', inv_date_color='#9a8070',
        divider=None,
        client_bg='#fefaf8', client_border='#f0ddd8',
        period_label='Week Of',
        row_even='#ffffff', row_odd='#fdf8f4',
        total_style='inline',
        total_border='#e8c8cd',
        total_summary_color='#9a8070',
        total_amount_font='Times-Bold', total_amount_color='#b76e79',
        footer_bg='#f8eded', footer_border='#f0ddd8',
    ),
    'caring-hands': dict(
        accent='#7ab5a8', dark='#1a2a3a', med='#4a6a60', light='#7a9a90',
        page_bg=None,
        header_bg='#1a2a3a', header_border=None,
        name_font='Helvetica-Bold', name_color='#ffffff',
        detail_color='#8aacaa',
        inv_num_color='#ffffff', inv_date_color='#8aacaa',
        divider='gradient',
        divider_color='#7ab5a8',
        client_bg='#f4f8f8', client_border='#e0eeec',
        period_label='Service Period',
        row_even='#ffffff', row_odd='#f4f9f8',
        total_style='box',
        total_box_bg='#1a2a3a', total_box_label='#7ab5a8',
        total_box_amount='#ffffff',
        footer_bg=None, footer_border='#d8eae8',
    ),
    'garden': dict(
        accent='#5a8a5a', dark='#2d4a2d', med='#6a8a60', light='#7a9a70',
        page_bg='#fffef8',
        header_bg='#2d4a2d', header_border=None,
        name_font='Helvetica', name_color='#e8f5e4',
        detail_color='#a8c8a0',
        inv_num_color='#ffffff', inv_date_color='#a8c8a0',
        inv_box_bg='#4a7a4a',
        divider='botanical',
        divider_bg='#5a8a5a', divider_text='#c8e8c0',
        client_bg='#f6fbf4', client_border='#d0e8c8',
        period_label='Service Week',
        row_even='#fffef8', row_odd='#f4f8f0',
        total_style='dashed',
        total_border='#b8d8b0',
        total_summary_color='#7a9a70',
        total_amount_font='Helvetica-Bold', total_amount_color='#2d4a2d',
        footer_bg='#f0f8ec', footer_border='#c0d8b8',
    ),
}


# ── Validation helpers ─────────────────────────────────────────────────

def _validate_config(config, required_keys):
    """
    Validate that all required keys are present in config dictionary.

    Args:
        config: dict, configuration dictionary to validate
        required_keys: list of str, required key names

    Raises:
        ValueError: if any required key is missing
    """
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(
            f"Missing required config keys: {', '.join(missing_keys)}"
        )


def _calculate_weekly_totals(hours, rate):
    """
    Calculate total hours and total pay from hours dictionary.

    Args:
        hours: dict mapping day names to hour counts
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


# ── Drawing primitives ─────────────────────────────────────────────────
# All "top" parameters = distance in points from the top of the page.

def _rect(c, x, top, w, h, color):
    """Draw a filled rectangle."""
    c.setFillColor(HexColor(color) if isinstance(color, str) else color)
    c.rect(x, PAGE_H - top - h, w, h, fill=1, stroke=0)


def _rrect(c, x, top, w, h, r, color):
    """Draw a filled rounded rectangle."""
    c.setFillColor(HexColor(color) if isinstance(color, str) else color)
    c.roundRect(x, PAGE_H - top - h, w, h, r, fill=1, stroke=0)


def _hline(c, x1, x2, top, color, width=1, dash=None):
    """Draw a horizontal line."""
    c.setStrokeColor(HexColor(color) if isinstance(color, str) else color)
    c.setLineWidth(width)
    if dash:
        c.setDash(dash[0], dash[1])
    else:
        c.setDash(1, 0)
    c.line(x1, PAGE_H - top, x2, PAGE_H - top)


def _txt(c, x, top, text, font='Helvetica', size=12, color='#000000'):
    """Draw left-aligned text. top = distance from page top to baseline."""
    c.setFont(font, size)
    c.setFillColor(HexColor(color) if isinstance(color, str) else color)
    c.drawString(x, PAGE_H - top, str(text))


def _txt_r(c, x, top, text, font='Helvetica', size=12, color='#000000'):
    """Draw right-aligned text."""
    c.setFont(font, size)
    c.setFillColor(HexColor(color) if isinstance(color, str) else color)
    c.drawRightString(x, PAGE_H - top, str(text))


def _txt_center(c, top, text, font='Helvetica', size=12, color='#000000'):
    """Draw centered text on the page."""
    c.setFont(font, size)
    c.setFillColor(HexColor(color) if isinstance(color, str) else color)
    c.drawCentredString(PAGE_W / 2, PAGE_H - top, str(text))


# ── Weekly invoice drawing ─────────────────────────────────────────────

def _draw_weekly(c, config, hours, week, total_hours, total_pay, tid):
    """Draw a complete weekly invoice on the canvas."""
    t = THEMES[tid]
    rate = config['rate']

    # Page background
    if t['page_bg']:
        _rect(c, 0, 0, PAGE_W, PAGE_H, t['page_bg'])

    y = 0  # current vertical position from top

    # ── Header ──
    header_h = 104
    _rect(c, 0, y, PAGE_W, header_h, t['header_bg'])

    if t['header_border']:
        _hline(c, 0, PAGE_W, y + header_h, t['header_border'], width=4)

    # Subtitle label
    _txt(c, MARGIN, y + 44, 'HOME HEALTH INVOICE',
         'Helvetica-Bold', 9, t['accent'])

    # Provider name
    _txt(c, MARGIN, y + 64, config['name'],
         t['name_font'], 22, t['name_color'])

    # Address and email
    _txt(c, MARGIN, y + 80, config['address'],
         'Helvetica', 11, t['detail_color'])
    _txt(c, MARGIN, y + 94, config['personalEmail'],
         'Helvetica', 11, t['detail_color'])

    # Invoice info (right side)
    inv_x = RIGHT

    # Garden: frosted box behind invoice info
    if tid == 'garden':
        _rrect(c, PAGE_W - MARGIN - 135, y + 26, 135, 64, 8,
               t['inv_box_bg'])
        inv_x = PAGE_W - MARGIN - 14

    _txt_r(c, inv_x, y + 44, 'INVOICE',
           'Helvetica', 8, t['accent'])
    _txt_r(c, inv_x, y + 60, week.get('invNum', ''),
           'Courier-Bold', 14, t['inv_num_color'])
    _txt_r(c, inv_x, y + 76, week.get('end', ''),
           'Helvetica', 11, t['inv_date_color'])

    y += header_h
    if t['header_border']:
        y += 4  # border thickness

    # ── Divider ──
    if t.get('divider') == 'gradient':
        _rect(c, 0, y, PAGE_W, 4, t['divider_color'])
        y += 4
    elif t.get('divider') == 'botanical':
        _rect(c, 0, y, PAGE_W, 18, t['divider_bg'])
        _txt(c, MARGIN, y + 13, u'\u2726  \u2726  \u2726',
             'Helvetica', 9, t['divider_text'])
        y += 18

    # ── Client info section ──
    client_h = 60
    _rect(c, 0, y, PAGE_W, client_h, t['client_bg'])
    _hline(c, 0, PAGE_W, y + client_h, t['client_border'])

    _txt(c, MARGIN, y + 22, 'BILLED TO',
         'Helvetica-Bold', 8, t['accent'])
    _txt(c, MARGIN, y + 36, config['clientName'],
         'Helvetica-Bold', 13, t['dark'])
    _txt(c, MARGIN, y + 50, config['clientEmail'],
         'Helvetica', 11, t['med'])

    period_x = 320
    _txt(c, period_x, y + 22, t['period_label'].upper(),
         'Helvetica-Bold', 8, t['accent'])
    _txt(c, period_x, y + 36,
         f"{week.get('start', '')} \u2013 {week.get('end', '')}",
         'Helvetica', 12, t['dark'])

    y += client_h + 1

    # ── Table header ──
    y += 6
    _txt(c, COL_DAY, y + 18, 'DAY',
         'Helvetica-Bold', 8, t['accent'])
    _txt_r(c, COL_HOURS, y + 18, 'HOURS',
           'Helvetica-Bold', 8, t['accent'])
    _txt_r(c, COL_RATE, y + 18, 'RATE',
           'Helvetica-Bold', 8, t['accent'])
    _txt_r(c, COL_AMOUNT, y + 18, 'AMOUNT',
           'Helvetica-Bold', 8, t['accent'])
    y += 26
    _hline(c, 0, PAGE_W, y, t['client_border'], width=1)
    y += 1

    # ── Table rows ──
    row_h = 26
    visible_row = 0
    day_dates = week.get('dayDates') or {}

    for day in DAYS:
        day_hours = hours.get(day, 0)
        if day_hours <= 0:
            continue

        row_bg = t['row_even'] if visible_row % 2 == 0 else t['row_odd']
        _rect(c, 0, y, PAGE_W, row_h, row_bg)

        # Day name
        _txt(c, COL_DAY, y + 18, day, 'Helvetica', 12, t['dark'])

        # Day date annotation
        dd = day_dates.get(day, '')
        if dd:
            day_w = c.stringWidth(day, 'Helvetica', 12)
            _txt(c, COL_DAY + day_w + 8, y + 18, dd,
                 'Helvetica', 9, t['accent'])

        # Hours, rate, amount
        _txt_r(c, COL_HOURS, y + 18, str(day_hours),
               'Helvetica', 12, t['dark'])
        _txt_r(c, COL_RATE, y + 18, f'${rate:.2f}',
               'Helvetica', 12, t['accent'])
        _txt_r(c, COL_AMOUNT, y + 18, f'${day_hours * rate:.2f}',
               'Helvetica-Bold', 12, t['dark'])

        y += row_h
        visible_row += 1

    y += 10

    # ── Total section ──
    if t['total_style'] == 'box':
        # Caring Hands: dark navy rounded box, right-aligned
        box_w = 210
        box_h = 54
        box_x = RIGHT - box_w
        _rrect(c, box_x, y, box_w, box_h, 10, t['total_box_bg'])
        _txt_r(c, RIGHT - 18, y + 22,
               f'{total_hours} hours \u00b7 Total Due',
               'Helvetica', 9, t['total_box_label'])
        _txt_r(c, RIGHT - 18, y + 44, f'${total_pay}',
               'Helvetica-Bold', 26, t['total_box_amount'])
        y += box_h + 14
    else:
        # Morning Light / Garden: inline with border
        dash = (6, 3) if t['total_style'] == 'dashed' else None
        _hline(c, MARGIN, RIGHT, y, t['total_border'], width=2, dash=dash)
        y += 6

        _txt(c, MARGIN, y + 20,
             f'{total_hours} hrs \u00b7 ${rate:.2f}/hr',
             'Helvetica', 11, t['total_summary_color'])

        _txt_r(c, RIGHT, y + 10, 'TOTAL DUE',
               'Helvetica', 8, t['accent'])
        _txt_r(c, RIGHT, y + 36, f'${total_pay}',
               t['total_amount_font'], 26, t['total_amount_color'])
        y += 50

    # ── Footer ──
    y += 4
    footer_h = 34
    if t['footer_bg']:
        _rect(c, 0, y, PAGE_W, footer_h, t['footer_bg'])
    _hline(c, 0, PAGE_W, y, t['footer_border'])

    note = config.get('invoiceNote', '')
    _txt_center(c, y + 22, note, 'Helvetica-Oblique', 10, t['light'])


# ── Monthly report drawing ─────────────────────────────────────────────

def _draw_monthly(c, config, week_data, month_label, total_hours,
                  total_pay, weeks_worked):
    """Draw a complete monthly summary report on the canvas."""
    rate = config['rate']

    y = 0

    # ── Header ──
    header_h = 104
    _rect(c, 0, y, PAGE_W, header_h, '#2c3e50')

    _txt(c, MARGIN, y + 44, 'MONTHLY HOURS SUMMARY',
         'Helvetica-Bold', 9, '#a8c8d8')
    _txt(c, MARGIN, y + 64, config['name'],
         'Helvetica-Bold', 22, '#ffffff')
    _txt(c, MARGIN, y + 80, config['address'],
         'Helvetica', 11, '#8aacbc')
    _txt(c, MARGIN, y + 94, config['personalEmail'],
         'Helvetica', 11, '#8aacbc')

    _txt_r(c, RIGHT, y + 44, 'REPORT PERIOD',
           'Helvetica', 8, '#a8c8d8')
    _txt_r(c, RIGHT, y + 64, month_label,
           'Helvetica-Bold', 16, '#ffffff')

    y += header_h

    # ── Accent bar ──
    _rect(c, 0, y, PAGE_W, 4, '#7ab5c8')
    y += 4

    # ── Info section (client, accountant, rate) ──
    info_h = 58
    _rect(c, 0, y, PAGE_W, info_h, '#f4f8fa')
    _hline(c, 0, PAGE_W, y + info_h, '#d8eaf0')

    # Submitted To
    _txt(c, MARGIN, y + 20, 'SUBMITTED TO',
         'Helvetica-Bold', 8, '#5a90a8')
    _txt(c, MARGIN, y + 34, config['clientName'],
         'Helvetica-Bold', 11, '#1a2a3a')
    _txt(c, MARGIN, y + 47, config['clientEmail'],
         'Helvetica', 10, '#4a6a70')

    # Prepared For
    col2 = 220
    _txt(c, col2, y + 20, 'PREPARED FOR',
         'Helvetica-Bold', 8, '#5a90a8')
    _txt(c, col2, y + 34, 'Accountant of Record',
         'Helvetica-Bold', 11, '#1a2a3a')
    _txt(c, col2, y + 47, config.get('accountantEmail', ''),
         'Helvetica', 10, '#4a6a70')

    # Rate
    col3 = 420
    _txt(c, col3, y + 20, 'RATE',
         'Helvetica-Bold', 8, '#5a90a8')
    _txt(c, col3, y + 36, f'${rate:.2f}',
         'Helvetica-Bold', 14, '#1a2a3a')
    _txt(c, col3 + c.stringWidth(f'${rate:.2f}', 'Helvetica-Bold', 14) + 2,
         y + 36, '/hr', 'Helvetica', 9, '#5a8090')

    y += info_h + 1

    # ── Week-by-week table header ──
    y += 6
    _txt(c, MCOL_WEEK, y + 18, 'WEEK',
         'Helvetica-Bold', 8, '#5a90a8')
    _txt(c, MCOL_PERIOD, y + 18, 'PERIOD',
         'Helvetica-Bold', 8, '#5a90a8')
    _txt_r(c, MCOL_HOURS, y + 18, 'HOURS',
           'Helvetica-Bold', 8, '#5a90a8')
    _txt_r(c, MCOL_RATE, y + 18, 'RATE',
           'Helvetica-Bold', 8, '#5a90a8')
    _txt_r(c, MCOL_AMOUNT, y + 18, 'AMOUNT',
           'Helvetica-Bold', 8, '#5a90a8')
    y += 26
    _hline(c, 0, PAGE_W, y, '#d8eaf0', width=1)
    y += 1

    # ── Table rows ──
    row_h = 26
    for i, wk in enumerate(week_data):
        wk_hours = wk.get('hours', 0)
        is_zero = wk_hours == 0

        row_bg = '#ffffff' if i % 2 == 0 else '#f6fbfd'
        _rect(c, 0, y, PAGE_W, row_h, row_bg)

        # Use lighter colors for zero-hour weeks
        text_color = '#b0b0b0' if is_zero else '#1a2a3a'
        label_color = '#b0b0b0' if is_zero else '#4a6a70'
        rate_color = '#c0c0c0' if is_zero else '#5a90a8'

        _txt(c, MCOL_WEEK, y + 18, f'Week {i + 1}',
             'Helvetica-Bold', 11, text_color)
        _txt(c, MCOL_PERIOD, y + 18, wk.get('label', ''),
             'Helvetica', 10, label_color)
        _txt_r(c, MCOL_HOURS, y + 18, str(wk_hours),
               'Helvetica', 11, text_color)
        _txt_r(c, MCOL_RATE, y + 18, f'${rate:.2f}',
               'Helvetica', 11, rate_color)

        if wk_hours > 0:
            _txt_r(c, MCOL_AMOUNT, y + 18, f'${wk_hours * rate:.2f}',
                   'Helvetica-Bold', 11, text_color)
        else:
            _txt_r(c, MCOL_AMOUNT, y + 18, '\u2014',
                   'Helvetica', 11, '#aaaaaa')

        y += row_h

    y += 14

    # ── Summary section ──
    # Left: weeks worked summary
    wk_word = 'week' if weeks_worked == 1 else 'weeks'
    _txt(c, MARGIN, y + 36,
         f'{weeks_worked} {wk_word} worked \u00b7 ${rate:.2f}/hr',
         'Helvetica', 11, '#7a9aaa')

    # Right: dark box with total
    box_w = 220
    box_h = 54
    box_x = RIGHT - box_w
    _rrect(c, box_x, y, box_w, box_h, 10, '#2c3e50')
    _txt_r(c, RIGHT - 18, y + 22,
           f'{total_hours} total hours \u00b7 Amount Due',
           'Helvetica', 9, '#a8c8d8')
    _txt_r(c, RIGHT - 18, y + 44, f'${total_pay}',
           'Helvetica-Bold', 26, '#ffffff')
    y += box_h + 14

    # ── Signature lines ──
    _hline(c, MARGIN, RIGHT, y, '#c8dce8', width=1, dash=(4, 3))
    y += 14

    _txt(c, MARGIN, y + 12, 'PROVIDER SIGNATURE',
         'Helvetica', 8, '#5a90a8')
    _hline(c, MARGIN, MARGIN + 200, y + 34, '#1a2a3a')
    _txt(c, MARGIN, y + 46, config['name'],
         'Helvetica', 9, '#7a9aaa')

    date_x = 320
    _txt(c, date_x, y + 12, 'DATE',
         'Helvetica', 8, '#5a90a8')
    _hline(c, date_x, date_x + 150, y + 34, '#1a2a3a')

    y += 60

    # ── Footer ──
    footer_h = 32
    _rect(c, 0, y, PAGE_W, footer_h, '#f4f8fa')
    _hline(c, 0, PAGE_W, y, '#d8eaf0')
    _txt_center(c, y + 20,
                'This summary is provided for accounting and tax purposes. '
                'Weekly invoices are available upon request.',
                'Helvetica-Oblique', 9, '#7a9aaa')


# ── Public API ─────────────────────────────────────────────────────────

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
            - dayDates: dict mapping day names to short dates
        template_id: str, template variant identifier
            - 'morning-light', 'caring-hands', or 'garden'

    Returns:
        bytes: PDF file contents

    Raises:
        ValueError: if template_id is invalid or required config keys missing
    """
    required_keys = ['name', 'address', 'personalEmail', 'rate',
                     'clientName', 'clientEmail', 'invoiceNote']
    _validate_config(config, required_keys)

    if template_id not in WEEKLY_TEMPLATES:
        raise ValueError(
            f"Invalid template_id '{template_id}'. "
            f"Must be one of: {', '.join(WEEKLY_TEMPLATES.keys())}"
        )

    total_hours, total_pay = _calculate_weekly_totals(hours, config['rate'])

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _draw_weekly(c, config, hours, week, total_hours, total_pay, template_id)
    c.save()
    return buf.getvalue()


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
            - Each dict: {'label': str, 'hours': int}
        month_label: str, month and year (e.g., "March 2026")

    Returns:
        bytes: PDF file contents

    Raises:
        ValueError: if required config keys are missing
    """
    required_keys = ['name', 'address', 'personalEmail', 'rate',
                     'clientName', 'clientEmail', 'accountantEmail']
    _validate_config(config, required_keys)

    total_hours, total_pay, weeks_worked = _calculate_monthly_totals(
        week_data, config['rate']
    )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _draw_monthly(c, config, week_data, month_label, total_hours,
                  total_pay, weeks_worked)
    c.save()
    return buf.getvalue()
