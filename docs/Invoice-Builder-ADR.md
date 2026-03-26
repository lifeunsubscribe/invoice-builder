# ADR: lisa-invoice-app
**Status:** Approved  
**Date:** 2026-03-26  
**Author:** Sarah (developer), for Lisa Wadley (end user)

---

## Context

Lisa is a 1099 home health aide contractor who submits weekly invoices to her client agency and forwards a monthly summary to her accountant. She is non-technical, uses a Windows HP laptop, and has zero tolerance for apps that require ongoing maintenance or remembering steps. The app must open like any other desktop program, require no terminal interaction, and work without any cloud dependency.

---

## Decision

Build a self-contained local desktop app that:
- Opens in the default browser at `localhost:5000` when she double-clicks a shortcut
- Presents a home menu with three options: Weekly Invoice, Monthly Report, Edit Profile
- Generates live PDF previews as she edits hours
- Emails PDFs via Gmail SMTP on "Save & Submit"
- Saves PDFs to a structured local folder derived from her name
- Scans existing saved invoices to pre-populate the monthly report
- Warns before overwriting an already-sent document
- Is packaged as a Windows `.exe` via PyInstaller — no Python install required

---

## Repository Structure

```
invoice-builder/
├── frontend/
│   ├── src/
│   │   └── App.jsx              ← Complete UI (v10 — do not restructure)
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── app/
│   ├── main.py                  ← Flask entry point, serves /dist, registers blueprints
│   ├── api/
│   │   ├── config_api.py        ← GET/POST /api/config
│   │   ├── scan_api.py          ← GET /api/scan, GET /api/scan-month
│   │   └── submit_api.py        ← POST /api/submit/weekly, POST /api/submit/monthly
│   ├── services/
│   │   ├── pdf_service.py       ← WeasyPrint HTML→PDF rendering
│   │   ├── mail_service.py      ← smtplib email with PDF attachment
│   │   └── folder_service.py    ← Folder creation, path helpers, file scanning
│   └── templates/
│       └── (WeasyPrint HTML templates — weekly and monthly)
├── dist/                        ← Vite build output (gitignored, bundled by PyInstaller)
├── config.example.json
├── .env.example
├── config.json                  ← NOT in git
├── .env                         ← NOT in git
├── requirements.txt
├── build.bat
└── README.md
```

**`.gitignore` must include:**
```
config.json
.env
dist/
build/
__pycache__/
*.pyc
*.spec
node_modules/
```

---

## Tech Stack

| Concern | Choice | Rationale |
|---|---|---|
| Frontend framework | React 18 + Vite | Complete UI already built; Vite gives fast dev iteration and clean static build |
| Backend | Flask | Lightweight, minimal boilerplate, easy to bundle with PyInstaller |
| PDF generation | WeasyPrint | HTML+CSS → PDF; matches the existing template aesthetic exactly. **Note:** requires GTK on Windows — test bundling carefully; fall back to ReportLab if PyInstaller bundling fails |
| Email | smtplib (stdlib) | No extra dependency; Gmail SMTP + app password, free forever |
| Persistence | config.json (flat file) | No database needed; settings rarely change |
| Packaging | PyInstaller `--onefile --windowed` | Single `.exe`, no Python install required on her machine |
| Frontend → Backend comms | `fetch()` to Flask REST endpoints | Replace all `setTimeout` simulation stubs in App.jsx with real fetch calls |

---

## Frontend Architecture

**The UI is complete.** `frontend/src/App.jsx` (v10) contains the full React application including all pages, state management, PDF templates, and component logic. The only frontend changes required during backend integration are:

1. Replace `setTimeout` simulation blocks with `fetch()` calls to Flask endpoints
2. Pass `config` initial state from `GET /api/config` on app mount instead of `defaultConfig`

**Do not restructure components, rename pages, or rewrite templates.** The component tree is intentional.

### Pages
- `LandingPage` — home menu, "Saving to" pill navigates to Profile folder section
- `WeeklyPage` — invoice editor with week navigation (‹/›), template switcher, zoom, saved status pill
- `MonthlyPage` — monthly report editor with month navigation, scan popup on load
- `ProfilePage` — all editable fields + color picker + folder preview; scroll-to-folder supported via `scrollToFolder` prop

### PDF Templates (rendered in-browser for preview, rendered server-side for actual PDF)
- `TemplateMorningLight` — fixed rose palette `#b76e79`, warm cream gradient header
- `TemplateCaringHands` — fixed teal `#7ab5a8`, dark navy `#1a2a3a` header
- `TemplateGarden` — fixed forest green `#5a8a5a`, botanical header with ✦ divider
- `MonthlyReportPDF` — slate blue `#2c3e50`, accountant-oriented week-by-week table with signature line

Templates use **fixed accent colors** — they do not respond to the user's palette setting. The palette setting only affects the editor chrome (buttons, totals chip, submit button, title bar accent).

---

## Configuration Schema

### `config.json` (never committed)
```json
{
  "name": "Lisa Wadley",
  "address": "123 Main St, Denver, CO 80201",
  "personalEmail": "lisa@email.com",
  "rate": 28.00,
  "clientName": "Sunrise Home Health Agency",
  "clientEmail": "billing@sunrisehh.com",
  "accountantEmail": "accountant@cpa.com",
  "accent": "#b76e79",
  "invoiceNote": "Thank you for the privilege of caring for your clients.",
  "saveFolder": "~/Documents/lisa-w-invoices"
}
```

### `.env` (never committed)
```
GMAIL_ADDRESS=lisa@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

### Save Folder Derivation
Derived automatically from `name` unless manually overridden in Profile:
- `"Lisa Wadley"` → `~/Documents/lisa-w-invoices`
- `"Lisa Marie Wadley"` → `~/Documents/lisa-w-invoices` (middle name ignored)
- `"Jane Doe"` → `~/Documents/jane-d-invoices`

**Logic:** take first name (lowercased) + first letter of last token (lowercased) + `-invoices`.

Profile page shows a "↺ Reset to auto-derived" link when manually overridden.

---

## File System Conventions

```
{saveFolder}/
├── weekly/
│   ├── INV-20260324.pdf       ← week of Mon Mar 24
│   ├── INV-20260317.pdf
│   └── ...
└── monthly/
    ├── RPT-2026-03.pdf        ← March 2026 monthly report
    ├── RPT-2026-02.pdf
    └── ...
```

**Weekly invoice filename:** `INV-YYYYMMDD.pdf` where the date is the Monday of that week.  
**Monthly report filename:** `RPT-YYYY-MM.pdf`

Both folders are created automatically on first save if they don't exist (`os.makedirs(path, exist_ok=True)`).

---

## Flask API Endpoints

### `GET /api/config`
Returns current `config.json` contents as JSON. Called on app mount to hydrate React state.

### `POST /api/config`
Accepts full config object, writes to `config.json`. Called when Profile "Save Profile" is pressed.

### `GET /api/scan?folder=<path>&invNum=<INV-YYYYMMDD>`
Checks whether `{folder}/weekly/{invNum}.pdf` exists.  
Returns: `{ "found": true|false }`  
Used by: Weekly page (not currently used — weekly defaults to 8/day, no scan)

### `GET /api/scan-month?year=<YYYY>&month=<M>&folder=<path>`
For each Mon–Sun week overlapping the given month, checks whether the corresponding `INV-YYYYMMDD.pdf` exists in `{folder}/weekly/`.  
Returns:
```json
{
  "weeks": [
    { "label": "Mar 3 – Mar 9, 2026", "invNum": "INV-20260303", "found": true, "hours": 40 },
    { "label": "Mar 10 – Mar 16, 2026", "invNum": "INV-20260310", "found": false, "hours": 0 }
  ]
}
```
If `found: true`, parse the PDF to extract total hours (or store a sidecar `.json` with hours metadata alongside each PDF — simpler and more reliable than PDF parsing).

**Recommendation:** write a `{invNum}.json` sidecar file alongside each weekly PDF containing `{ "totalHours": 40, "dailyHours": {...} }`. Avoids PDF parsing entirely.

### `POST /api/submit/weekly`
Payload:
```json
{
  "hours": { "Monday": 8, "Tuesday": 8, ... },
  "clientEmail": "billing@...",
  "accountantEmail": "accountant@...",
  "week": { "start": "March 24", "end": "March 30, 2026", "invNum": "INV-20260324" },
  "template": "morning-light"
}
```
Actions:
1. Render HTML invoice using the specified template + config data
2. Generate PDF with WeasyPrint → save to `{saveFolder}/weekly/{invNum}.pdf`
3. Write sidecar JSON: `{saveFolder}/weekly/{invNum}.json` with hours data
4. Send email to `clientEmail` and `accountantEmail` with PDF attached
5. Return `{ "success": true, "saved": "<path>", "sent": ["...", "..."] }`

### `POST /api/submit/monthly`
Payload:
```json
{
  "weekData": [
    { "label": "Mar 3 – Mar 9", "hours": 40 },
    ...
  ],
  "year": 2026,
  "month": 2,
  "accountantEmail": "accountant@..."
}
```
Actions:
1. Render monthly report HTML
2. Generate PDF → save to `{saveFolder}/monthly/RPT-{YYYY}-{MM}.pdf`
3. Send to `accountantEmail` only
4. Return `{ "success": true, "saved": "<path>", "sent": ["..."] }`

---

## PDF Generation

Use WeasyPrint to render HTML strings to PDF. Maintain two HTML template files in `app/templates/`:
- `invoice_weekly.html` — mirrors the active React template's layout (Morning Light, Caring Hands, or Garden)
- `invoice_monthly.html` — mirrors `MonthlyReportPDF` layout

Template variables injected via Jinja2 before passing to WeasyPrint. Fonts should be embedded or use system fonts for portability.

**PyInstaller + WeasyPrint on Windows:** WeasyPrint requires GTK. Use the `weasyprint` Windows installer or bundle with `--collect-all weasyprint`. If bundling proves unreliable, **fall back to ReportLab** — more verbose Python but zero native dependencies.

---

## Email Logic

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
```

Plain text body for weekly invoices:
```
Hi,

Please find attached my invoice for the week of [Mon] – [Sun].

Total hours: XX
Total due: $XXX.XX

Thank you,
[Name]
```

Plain text body for monthly reports:
```
Hi [Accountant Name],

Attached is my monthly hours summary for [Month Year].

Total hours: XX
Total invoiced: $XXX.XX

Please let me know if you need the individual weekly invoices as well.

Thank you,
[Name]
```

On email failure: return `{ "success": false, "error": "...", "saved": "<path>" }`. The PDF should always be saved locally even if email fails. Display a user-friendly error in the UI — do not silently fail.

---

## Frontend ↔ Backend Integration Points

The `setTimeout` simulation stubs in App.jsx map directly to these fetch calls:

| Simulation in App.jsx | Replace with |
|---|---|
| `setTimeout(()=>setScanPopup(results), 900)` in MonthlyPage | `fetch('/api/scan-month?year=&month=&folder=').then(r=>r.json()).then(data=>setScanPopup(data.weeks))` |
| `setTimeout(()=>setNotification({...}), 500)` in WeeklyPage doSend | `fetch('/api/submit/weekly', {method:'POST', body: JSON.stringify(payload)})` |
| `setTimeout(()=>setNotification({...}), 500)` in MonthlyPage doSend | `fetch('/api/submit/monthly', {method:'POST', body: JSON.stringify(payload)})` |
| `defaultConfig` hardcoded initial state | `useEffect(()=>{ fetch('/api/config').then(r=>r.json()).then(setConfig) }, [])` |
| Profile "Save Profile" button | Add `fetch('/api/config', {method:'POST', body: JSON.stringify(draft)})` before `onSave(draft); onBack()` |

---

## Flask Startup & Browser Launch

```python
import threading, webbrowser, time

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(port=5000, debug=False)
```

Flask serves the Vite `/dist` build as static files:
```python
app = Flask(__name__, static_folder="../dist", static_url_path="")

@app.route("/")
def index():
    return app.send_static_file("index.html")
```

---

## PyInstaller Packaging

**`build.bat`:**
```bat
@echo off
echo Building frontend...
cd frontend
npm run build
cd ..

echo Packaging executable...
pyinstaller --onefile --windowed ^
  --icon=frontend/public/icon.ico ^
  --name="LisaInvoice" ^
  --add-data "dist;dist" ^
  app/main.py

echo Done. Executable is in /dist/LisaInvoice.exe
pause
```

`--windowed` suppresses the console window on Windows. `--add-data "dist;dist"` bundles the Vite build output into the exe.

**After build:** test the `.exe` on a clean machine (or VM) before sending to Lisa. The SmartScreen warning on first run is expected — right-click → Run anyway, or: More info → Run anyway.

---

## App Icon

Receipt with a small heart. Design options:
- Create SVG, convert to multi-resolution `.ico` using Pillow at build time
- Or use RealFaviconGenerator (free, no code) — upload SVG, download `.ico`

Sizes needed: 16×16, 32×32, 48×48, 256×256.

---

## Installation for Lisa (Remote)

1. Build `LisaInvoice.exe` locally via `build.bat`
2. Pre-fill `config.json` with her real name, rate, and emails before building (cleaner first-run experience)
3. Upload `.exe` to a shared Google Drive folder
4. Phone call walkthrough (~10 min):
   - Download to Desktop
   - SmartScreen: More info → Run anyway (one-time only)
   - Browser opens automatically — she's in
   - Walk her through Profile to verify settings
5. She right-clicks the `.exe` → Send to → Desktop (create shortcut)

---

## Suggested Git Issues (Roadmap to Shipping)

These issues represent the complete remaining work. Feed this ADR + `App.jsx` to your local AI and use these as the issue backlog.

**Setup**
- [ ] `[setup]` Initialize Vite + React project in `/frontend`, copy App.jsx as entry point
- [ ] `[setup]` Initialize Flask project in `/app`, configure static file serving from `/dist`
- [ ] `[setup]` Add `config.example.json` and `.env.example` with documented placeholder values
- [ ] `[setup]` Write `build.bat` for Vite build + PyInstaller packaging

**Backend: Config**
- [ ] `[api]` Implement `GET /api/config` — read and return `config.json`
- [ ] `[api]` Implement `POST /api/config` — validate and write `config.json`
- [ ] `[service]` Implement `deriveSaveFolder(name)` in Python matching frontend logic exactly

**Backend: File System**
- [ ] `[service]` Implement folder creation on first save (`weekly/` and `monthly/` subdirs)
- [ ] `[service]` Implement sidecar JSON writer for weekly invoices `{invNum}.json`
- [ ] `[api]` Implement `GET /api/scan-month` — scan weekly folder, return per-week found/hours

**Backend: PDF**
- [ ] `[pdf]` Build `invoice_weekly.html` Jinja2 template matching Morning Light layout
- [ ] `[pdf]` Build `invoice_weekly.html` variants for Caring Hands and Garden templates
- [ ] `[pdf]` Build `invoice_monthly.html` Jinja2 template matching MonthlyReportPDF layout
- [ ] `[pdf]` Implement `pdf_service.py` — render HTML → PDF via WeasyPrint; include fallback notes for ReportLab

**Backend: Email**
- [ ] `[email]` Implement `mail_service.py` — Gmail SMTP, attach PDF, plain text body
- [ ] `[email]` Handle send failure gracefully — save PDF locally regardless, return error to frontend

**Backend: Submit Endpoints**
- [ ] `[api]` Implement `POST /api/submit/weekly` — generate PDF, write sidecar, send emails, return status
- [ ] `[api]` Implement `POST /api/submit/monthly` — generate PDF, send to accountant only, return status

**Frontend Integration**
- [ ] `[integration]` Replace `defaultConfig` with `GET /api/config` fetch on app mount
- [ ] `[integration]` Wire Profile "Save Profile" to `POST /api/config`
- [ ] `[integration]` Replace Monthly scan `setTimeout` with `GET /api/scan-month` fetch
- [ ] `[integration]` Replace Weekly `doSend` `setTimeout` with `POST /api/submit/weekly` fetch
- [ ] `[integration]` Replace Monthly `doSend` `setTimeout` with `POST /api/submit/monthly` fetch
- [ ] `[integration]` Handle API error responses in UI — show user-friendly error state

**Packaging**
- [ ] `[packaging]` Test PyInstaller + WeasyPrint bundling on Windows; document GTK path or switch to ReportLab
- [ ] `[packaging]` Create app icon (receipt + heart) as multi-resolution `.ico`
- [ ] `[packaging]` Full end-to-end test on clean Windows machine
- [ ] `[packaging]` Write one-page install guide for Lisa

---

## What Is NOT In Scope

- Cloud sync, remote access, or mobile access
- User authentication
- Multiple users, clients, or rates
- Invoice editing after sending
- Drag-and-drop template editor
- Any UI that requires her to touch a terminal
- Automatic invoice generation without her review (she always approves before sending)
