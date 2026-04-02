"""
app/themes.py — Theme Registry for Invoice Builder

Central source of truth for all template palettes and metadata.
Used by:
  - pdf_service.py  →  template file mapping + Jinja2 context injection
  - /api/themes     →  React frontend chrome theming (GET endpoint to expose)
  - Profile picker  →  display label, emoji, structure hint

Theme structures:
  'light-header'  — gradient on white, solid accent border-bottom (Morning Light, Golden Hour, Coastal)
  'dark-header'   — solid dark background, accent gradient divider line (Caring Hands, Lavender Eve)
  'botanical'     — dark gradient header, ✦ divider strip, dashed total separator (Garden, Terracotta)

Adding a new theme:
  1. Add entry to THEMES dict below
  2. Add theme ID to THEME_ORDER list
  3. Create template files:
       app/templates/invoice_{id_underscored}.html
       app/templates/invoice_monthly_{id_underscored}.html
       app/templates/invoice_log_{id_underscored}.html
  4. Restart the server — pdf_service.py picks up the new files automatically
"""

THEMES = {

    # ── MORNING LIGHT ─────────────────────────────────────────────────────────
    'morning-light': {
        'id': 'morning-light',
        'label': 'Morning Light',
        'emoji': '🌸',
        'structure': 'light-header',
        'font_style': 'serif',

        # PDF / Jinja2 palette
        'accent':               '#b76e79',
        'header_bg':            'linear-gradient(135deg, rgba(183, 110, 121, 0.16), rgba(183, 110, 121, 0.28))',
        'header_border':        '4px solid #b76e79',
        'header_accent_text':   '#b76e79',
        'header_name_color':    '#2c1810',
        'header_meta_color':    '#6a4a40',
        'header_invnum_color':  '#2c1810',
        'text_dark':            '#2c1810',
        'text_medium':          '#6a4a40',
        'text_light':           '#9a8070',
        'row_even':             'white',
        'row_odd':              '#fdf8f4',
        'info_bg':              '#fdf2f4',
        'info_border':          '#f0dce0',
        'total_bg':             None,
        'total_text':           '#2c1810',
        'footer_bg':            '#fdf2f4',
        'footer_text':          '#9a8070',
        'divider_bg':           None,
        'divider_text':         None,

        # React UI chrome
        'chrome_accent':        '#b76e79',
        'chrome_toolbar':       '#fdf8f4',
        'chrome_border':        '#f0dce0',
        'chrome_muted_text':    '#9a8070',
        'chrome_bg':            '#fdf8f4',
        'chrome_pill_active':   '#b76e79',
        'chrome_pill_text':     'white',
    },

    # ── CARING HANDS ──────────────────────────────────────────────────────────
    'caring-hands': {
        'id': 'caring-hands',
        'label': 'Caring Hands',
        'emoji': '🤍',
        'structure': 'dark-header',
        'font_style': 'sans',

        'accent':               '#7ab5a8',
        'header_bg':            '#1a2a3a',
        'header_border':        '3px solid #7ab5a8',
        'header_accent_text':   '#7ab5a8',
        'header_name_color':    'white',
        'header_meta_color':    '#8aacaa',
        'header_invnum_color':  'white',
        'text_dark':            '#1a2a3a',
        'text_medium':          '#4a6a60',
        'text_light':           '#7a9a90',
        'row_even':             'white',
        'row_odd':              '#f4f9f8',
        'info_bg':              '#f4f8f8',
        'info_border':          '#e0eeec',
        'total_bg':             '#1a2a3a',
        'total_text':           'white',
        'footer_bg':            'white',
        'footer_text':          '#7a9a90',
        'divider_bg':           None,
        'divider_text':         None,

        'chrome_accent':        '#7ab5a8',
        'chrome_toolbar':       '#f4f8f8',
        'chrome_border':        '#e0eeec',
        'chrome_muted_text':    '#7a9a90',
        'chrome_bg':            '#f4f8f8',
        'chrome_pill_active':   '#7ab5a8',
        'chrome_pill_text':     'white',
    },

    # ── GARDEN ────────────────────────────────────────────────────────────────
    'garden': {
        'id': 'garden',
        'label': 'Garden',
        'emoji': '🌿',
        'structure': 'botanical',
        'font_style': 'sans',

        'accent':               '#5a8a5a',
        'header_bg':            'linear-gradient(135deg, #2d4a2d, #3d6b3d)',
        'header_border':        'none',
        'header_accent_text':   '#a8d8a0',
        'header_name_color':    '#e8f5e4',
        'header_meta_color':    '#a8c8a0',
        'header_invnum_color':  'white',
        'text_dark':            '#2d4a2d',
        'text_medium':          '#6a8a60',
        'text_light':           '#7a9a70',
        'row_even':             '#fffef8',
        'row_odd':              '#f4f8f0',
        'info_bg':              '#f6fbf4',
        'info_border':          '#d0e8c8',
        'total_bg':             None,
        'total_text':           '#2d4a2d',
        'footer_bg':            '#f0f8ec',
        'footer_text':          '#7a9a70',
        'divider_bg':           '#5a8a5a',
        'divider_text':         '#c8e8c0',

        'chrome_accent':        '#5a8a5a',
        'chrome_toolbar':       '#f6fbf4',
        'chrome_border':        '#d0e8c8',
        'chrome_muted_text':    '#7a9a70',
        'chrome_bg':            '#f6fbf4',
        'chrome_pill_active':   '#5a8a5a',
        'chrome_pill_text':     'white',
    },

    # ── GOLDEN HOUR ───────────────────────────────────────────────────────────
    'golden-hour': {
        'id': 'golden-hour',
        'label': 'Golden Hour',
        'emoji': '☀️',
        'structure': 'light-header',
        'font_style': 'serif',

        'accent':               '#c4922a',
        'header_bg':            'linear-gradient(135deg, rgba(196, 146, 42, 0.32), rgba(196, 146, 42, 0.50))',
        'header_border':        '4px solid #c4922a',
        'header_accent_text':   '#c4922a',
        'header_name_color':    '#3a2600',
        'header_meta_color':    '#7a5020',
        'header_invnum_color':  '#3a2600',
        'text_dark':            '#3a2600',
        'text_medium':          '#7a5020',
        'text_light':           '#a87840',
        'row_even':             'white',
        'row_odd':              '#fdf8ee',
        'info_bg':              '#fdf5e8',
        'info_border':          '#e8d8b0',
        'total_bg':             None,
        'total_text':           '#3a2600',
        'footer_bg':            '#fdf5e8',
        'footer_text':          '#a87840',
        'divider_bg':           None,
        'divider_text':         None,

        'chrome_accent':        '#c4922a',
        'chrome_toolbar':       '#fdf8ee',
        'chrome_border':        '#e8d8b0',
        'chrome_muted_text':    '#a87840',
        'chrome_bg':            '#fdf8ee',
        'chrome_pill_active':   '#c4922a',
        'chrome_pill_text':     'white',
    },

    # ── LAVENDER EVE ──────────────────────────────────────────────────────────
    'lavender-eve': {
        'id': 'lavender-eve',
        'label': 'Lavender Eve',
        'emoji': '🌙',
        'structure': 'dark-header',
        'font_style': 'sans',

        'accent':               '#9b7fd4',
        'header_bg':            '#2a1f3d',
        'header_border':        '3px solid #9b7fd4',
        'header_accent_text':   '#c4b0f0',
        'header_name_color':    'white',
        'header_meta_color':    '#b0a0d0',
        'header_invnum_color':  'white',
        'text_dark':            '#2a1f3d',
        'text_medium':          '#5a4a70',
        'text_light':           '#8a7aa0',
        'row_even':             'white',
        'row_odd':              '#f8f5fd',
        'info_bg':              '#f5f2fd',
        'info_border':          '#e0d8f4',
        'total_bg':             '#2a1f3d',
        'total_text':           'white',
        'footer_bg':            'white',
        'footer_text':          '#8a7aa0',
        'divider_bg':           None,
        'divider_text':         None,

        'chrome_accent':        '#9b7fd4',
        'chrome_toolbar':       '#f8f5fd',
        'chrome_border':        '#e0d8f4',
        'chrome_muted_text':    '#8a7aa0',
        'chrome_bg':            '#f8f5fd',
        'chrome_pill_active':   '#9b7fd4',
        'chrome_pill_text':     'white',
    },

    # ── COASTAL ───────────────────────────────────────────────────────────────
    'coastal': {
        'id': 'coastal',
        'label': 'Coastal',
        'emoji': '🌊',
        'structure': 'light-header',
        'font_style': 'sans',

        'accent':               '#4a94b4',
        'header_bg':            'linear-gradient(135deg, rgba(74, 148, 180, 0.28), rgba(74, 148, 180, 0.45))',
        'header_border':        '4px solid #4a94b4',
        'header_accent_text':   '#4a94b4',
        'header_name_color':    '#0e2d3d',
        'header_meta_color':    '#2a6080',
        'header_invnum_color':  '#0e2d3d',
        'text_dark':            '#0e2d3d',
        'text_medium':          '#2a6080',
        'text_light':           '#5a8aa0',
        'row_even':             'white',
        'row_odd':              '#f0f8fc',
        'info_bg':              '#f0f8fc',
        'info_border':          '#c8e4f0',
        'total_bg':             None,
        'total_text':           '#0e2d3d',
        'footer_bg':            '#f0f8fc',
        'footer_text':          '#5a8aa0',
        'divider_bg':           None,
        'divider_text':         None,

        'chrome_accent':        '#4a94b4',
        'chrome_toolbar':       '#f0f8fc',
        'chrome_border':        '#c8e4f0',
        'chrome_muted_text':    '#5a8aa0',
        'chrome_bg':            '#f0f8fc',
        'chrome_pill_active':   '#4a94b4',
        'chrome_pill_text':     'white',
    },

    # ── TERRACOTTA ────────────────────────────────────────────────────────────
    'terracotta': {
        'id': 'terracotta',
        'label': 'Terracotta',
        'emoji': '🏺',
        'structure': 'botanical',
        'font_style': 'sans',

        # Fox orange variant
        'accent':               '#d4601a',
        'header_bg':            'linear-gradient(135deg, #4a1c06, #7a3010)',
        'header_border':        'none',
        'header_accent_text':   '#ffc090',
        'header_name_color':    '#fff0e8',
        'header_meta_color':    '#f0b880',
        'header_invnum_color':  'white',
        'text_dark':            '#3a1500',
        'text_medium':          '#8a4820',
        'text_light':           '#b87050',
        'row_even':             '#fffdf9',
        'row_odd':              '#fef3e8',
        'info_bg':              '#fef3e8',
        'info_border':          '#f0c090',
        'total_bg':             None,
        'total_text':           '#3a1500',
        'footer_bg':            '#fef3e8',
        'footer_text':          '#b87050',
        'divider_bg':           '#d4601a',
        'divider_text':         '#ffe0c0',

        'chrome_accent':        '#d4601a',
        'chrome_toolbar':       '#fff3e8',
        'chrome_border':        '#f0c090',
        'chrome_muted_text':    '#b87050',
        'chrome_bg':            '#fff3e8',
        'chrome_pill_active':   '#d4601a',
        'chrome_pill_text':     'white',
    },
}

# ── ORDERED LIST ──────────────────────────────────────────────────────────────
# Controls display order in the profile picker UI
THEME_ORDER = [
    'morning-light',
    'caring-hands',
    'garden',
    'golden-hour',
    'lavender-eve',
    'coastal',
    'terracotta',
]

# ── TEMPLATE FILE MAPS ────────────────────────────────────────────────────────
def _tmpl(prefix: str, theme_id: str) -> str:
    return f'{prefix}_{theme_id.replace("-", "_")}.html'

WEEKLY_TEMPLATE_FILES  = {tid: _tmpl('invoice', tid)         for tid in THEME_ORDER}
MONTHLY_TEMPLATE_FILES = {tid: _tmpl('invoice_monthly', tid) for tid in THEME_ORDER}
LOG_TEMPLATE_FILES     = {tid: _tmpl('invoice_log', tid)     for tid in THEME_ORDER}

# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_theme(theme_id: str) -> dict:
    """Return theme dict for given ID. Raises ValueError if unknown."""
    if theme_id not in THEMES:
        raise ValueError(
            f"Unknown theme_id '{theme_id}'. "
            f"Valid options: {', '.join(THEME_ORDER)}"
        )
    return THEMES[theme_id]


def get_all_themes() -> list:
    """Return all themes as a list in display order."""
    return [THEMES[tid] for tid in THEME_ORDER]


def get_chrome_palette(theme_id: str) -> dict:
    """Return only the chrome keys for a given theme — safe to expose via /api/themes."""
    t = get_theme(theme_id)
    return {
        'id':               t['id'],
        'label':            t['label'],
        'emoji':            t['emoji'],
        'structure':        t['structure'],
        'accent':           t['chrome_accent'],
        'toolbar':          t['chrome_toolbar'],
        'border':           t['chrome_border'],
        'mutedText':        t['chrome_muted_text'],
        'bg':               t['chrome_bg'],
        'pillActive':       t['chrome_pill_active'],
        'pillText':         t['chrome_pill_text'],
    }