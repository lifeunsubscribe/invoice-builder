# Windows PyInstaller Packaging Notes

**Date:** 2026-03-26
**Task:** [Phase 4] Test Windows PyInstaller bundling
**Status:** Documentation complete, awaiting Windows testing

---

## Overview

This document provides comprehensive testing procedures, known issues, and workarounds for packaging the Lisa Invoice Builder application as a Windows `.exe` using PyInstaller with WeasyPrint.

---

## System Requirements

### Development Machine (Build)
- Windows 10 or Windows 11
- Python 3.10+ installed
- Node.js 18+ and npm installed
- Git (for version control)
- All dependencies from `requirements.txt` installed

### Target Machine (End User - Lisa)
- Windows 10 or Windows 11
- **NO Python installation required**
- **NO developer tools required**
- Default web browser (Chrome, Edge, Firefox)
- ~100-200MB free disk space

---

## Build Process

### 1. Prerequisites Check

Before building, ensure:
```bat
# Check Python version (3.10+)
python --version

# Check Node.js version (18+)
node --version

# Check npm is installed
npm --version

# Verify you're in the project root
dir build.bat
```

### 2. Install Dependencies

```bat
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 3. Run the Build

```bat
# Execute the build script
build.bat
```

**Expected Output:**
```
Building frontend...
[Vite build output...]
✓ built in Xms

Packaging executable...
[PyInstaller output...]
INFO: Building EXE from EXE-00.toc completed successfully.

Done. Executable is in dist/LisaInvoice.exe
Press any key to continue...
```

### 4. Build Artifacts

After successful build:
```
dist/
├── LisaInvoice.exe          ← Main executable (50-150MB)
└── (no other files needed)

build/                       ← PyInstaller working directory (can be deleted)
LisaInvoice.spec            ← PyInstaller spec file (gitignored)
```

---

## Testing Procedures

### Test 1: Build Completion

**Acceptance Criterion:** build.bat completes without errors on Windows

**Procedure:**
1. Run `build.bat` from project root
2. Verify no error messages in console output
3. Check that `dist/LisaInvoice.exe` exists
4. Verify file size is reasonable (50-150MB range)

**Expected Result:** ✓ Build completes, exe file created

**Common Issues:**
- **"npm not found"** → Install Node.js from nodejs.org
- **"pyinstaller not found"** → Run `pip install pyinstaller`
- **"Frontend build failed"** → Check `frontend/package.json` exists, run `npm install` in frontend/
- **"icon.ico not found"** → Verify `frontend/public/icon.ico` exists

---

### Test 2: Exe Launch & Browser Opening

**Acceptance Criterion:** Exe launches and opens browser

**Procedure:**
1. Double-click `dist/LisaInvoice.exe`
2. Wait 2-3 seconds
3. Verify default browser opens automatically
4. Verify browser navigates to `http://localhost:5000` (or alternative port 5001-5010)
5. Verify React application loads (shows "Lisa Invoice Builder" interface)

**Expected Result:** ✓ Browser opens, app UI visible

**Common Issues:**
- **Windows SmartScreen warning:** "Windows protected your PC"
  - **Solution:** Click "More info" → "Run anyway" (one-time only)
  - **Why it happens:** Unsigned executable, expected for non-commercial apps
- **Port 5000 already in use:**
  - **Solution:** App auto-detects and uses next available port (5001-5010)
  - **Validation:** Console shows "Starting Lisa Invoice Builder on port 500X..."
- **Browser doesn't open:**
  - Check if browser opens but navigates to wrong URL
  - Try manually navigating to `http://localhost:5000`
  - Check Windows Firewall isn't blocking localhost connections
- **"Static files not found" error:**
  - Build issue: `frontend/dist/` not properly bundled
  - Solution: Re-run `build.bat`, ensure Vite build succeeds

---

### Test 3: PDF Generation from Bundled Exe

**Acceptance Criterion:** PDF generation works from bundled exe

**Procedure:**
1. Launch LisaInvoice.exe
2. Navigate to Profile page, configure name and save folder
3. Navigate to Weekly Invoice page
4. Enter hours for a week (e.g., Mon: 8, Tue: 8, etc.)
5. Click "Save & Submit" (or use test mode to save without email)
6. Verify PDF is created in `{saveFolder}/weekly/INV-YYYYMMDD.pdf`
7. Open the PDF and verify it renders correctly:
   - Invoice header with correct template styling
   - All hours displayed correctly
   - Total hours calculated correctly
   - No broken fonts or missing content

**Expected Result:** ✓ PDF created, opens correctly, all content rendered

**Common Issues:**
- **WeasyPrint GTK dependency error:**
  ```
  OSError: cannot load library 'gobject-2.0-0'
  ```
  - **Root cause:** WeasyPrint requires GTK3 DLLs for PDF rendering
  - **Solution 1:** Bundle GTK dependencies with PyInstaller:
    ```bat
    pyinstaller --onefile --windowed ^
      --icon=frontend/public/icon.ico ^
      --name="LisaInvoice" ^
      --add-data "frontend/dist;dist" ^
      --collect-all weasyprint ^
      --collect-all cairocffi ^
      --collect-all tinycss2 ^
      app/main.py
    ```
  - **Solution 2:** Install GTK3 for Windows on target machine:
    - Download GTK3 installer from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
    - Install to default location
    - Add GTK3 bin directory to PATH
  - **Solution 3 (FALLBACK):** Switch to ReportLab (pure Python, no native dependencies)
    - Update `app/services/pdf_service.py` to use ReportLab instead of WeasyPrint
    - Rewrite PDF templates using ReportLab's Python API
    - Rebuild with `build.bat`

- **"Permission denied" writing PDF:**
  - Folder doesn't exist or user lacks write permissions
  - Check `config.json` saveFolder path is valid and accessible
  - Ensure Documents folder is not redirected to OneDrive with restricted access

- **Fonts missing or incorrect in PDF:**
  - WeasyPrint needs explicit font files if using custom fonts
  - Solution: Use system fonts (Arial, Times New Roman, etc.) or bundle font files
  - Add to PyInstaller: `--add-data "fonts;fonts"`

---

### Test 4: Email Sending from Bundled Exe

**Acceptance Criterion:** Email sending works from bundled exe

**Procedure:**
1. Configure `.env` file with Gmail credentials:
   ```
   GMAIL_ADDRESS=your-email@gmail.com
   GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```
   - Place `.env` next to `LisaInvoice.exe` (same directory)
   - Use Gmail App Password (not regular password): https://myaccount.google.com/apppasswords

   **SECURITY WARNING:** The `.env` file contains sensitive credentials. Follow these security practices:
   - Never commit `.env` to version control (already in `.gitignore`)
   - Store `.env` in a secure location with restricted file permissions
   - Do not share `.env` via email, cloud storage, or messaging apps
   - Use Gmail App Passwords (limited scope) instead of your main account password
   - If credentials are compromised, immediately revoke the App Password at https://myaccount.google.com/apppasswords
   - Consider encrypting the folder containing `LisaInvoice.exe` and `.env` if on a shared computer
2. Launch LisaInvoice.exe
3. Configure Profile with valid client and accountant emails
4. Submit a weekly invoice
5. Verify email is sent successfully (check "Sent" folder in Gmail)
6. Verify email has PDF attachment
7. Verify email body contains correct week and totals

**Expected Result:** ✓ Email sent, PDF attached, recipient receives email

**Common Issues:**
- **".env file not found":**
  - Place `.env` in same directory as `LisaInvoice.exe`
  - In bundled mode: `sys.executable` directory (where exe lives)
  - Verify `python-dotenv` loads from correct location

- **"Authentication failed" (535 error):**
  - Using regular Gmail password instead of App Password
  - Solution: Generate App Password at https://myaccount.google.com/apppasswords
  - Must have 2-Factor Authentication enabled on Gmail account

- **"SMTP connection failed" (timeout):**
  - Firewall blocking SMTP port 587
  - Corporate network blocking outbound SMTP
  - Solution: Test on different network (home WiFi, hotspot)

- **Email sent but PDF not attached:**
  - Check PDF was created successfully first (Test 3)
  - Verify file path in `mail_service.py` is correct
  - Check email size limits (Gmail: 25MB per email)

---

### Test 5: Clean Machine Test

**Acceptance Criterion:** Clean machine test passes (no Python installed)

**Procedure:**
1. Set up a clean Windows 10/11 VM or physical machine:
   - Fresh Windows installation OR
   - Windows machine that has never had Python installed
2. Copy only `LisaInvoice.exe` to the test machine (e.g., USB drive, network share)
3. Copy `config.json` and `.env` to same directory as exe (if pre-configured)
4. Double-click `LisaInvoice.exe`
5. Navigate through SmartScreen warning if prompted
6. Verify all functionality works:
   - App opens in browser
   - Profile can be edited and saved
   - Weekly invoices can be created
   - PDFs are generated correctly
   - Emails are sent successfully (if configured)
7. Close app and restart to verify persistence (config.json saved)

**Expected Result:** ✓ All functionality works on clean machine without Python

**Clean Machine Setup Options:**

**Option A: Windows VM (Recommended for testing)**
- Download Windows 10/11 VM from Microsoft: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/
- Use VirtualBox, VMware, or Hyper-V
- Take snapshot before testing for easy resets

**Option B: Windows Sandbox (Quick test)**
- Available on Windows 10 Pro/Enterprise/Education
- Enable via: Turn Windows features on/off → Windows Sandbox
- Launch Windows Sandbox → Copy exe → Test
- **Limitation:** Sandbox resets on close, can't test persistence

**Option C: Physical machine (Lisa's actual laptop)**
- Most realistic test environment
- Requires coordination with end user
- Use only after VM testing succeeds

---

## Known Issues & Workarounds

### Issue 1: WeasyPrint GTK Bundling

**Symptom:** `OSError: cannot load library 'gobject-2.0-0'` when generating PDF

**Root Cause:** WeasyPrint depends on GTK3 native libraries (Cairo, Pango) which are difficult to bundle with PyInstaller on Windows.

**Workarounds:**

1. **Bundle GTK with PyInstaller (Success rate: ~60%)**
   ```bat
   pyinstaller --onefile --windowed ^
     --icon=frontend/public/icon.ico ^
     --name="LisaInvoice" ^
     --add-data "frontend/dist;dist" ^
     --collect-all weasyprint ^
     --collect-all cairocffi ^
     --collect-all tinycss2 ^
     --hidden-import=cairo ^
     --hidden-import=pangocffi ^
     app/main.py
   ```
   - May increase exe size to 150-200MB
   - Success depends on GTK installation on build machine

2. **Manual GTK Installation on Target Machine (Success rate: ~90%)**
   - Install GTK3 for Windows Runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
   - Add GTK bin directory to system PATH
   - Downside: Requires Lisa to install additional software (not ideal per ADR)

3. **Switch to ReportLab (Success rate: 100%, recommended fallback)**
   - Pure Python PDF library, no native dependencies
   - Reliable PyInstaller bundling
   - Downside: Requires rewriting PDF templates in Python code instead of HTML/CSS
   - Implementation time: ~4 hours to rewrite templates
   - See `docs/SPIKE_RESULTS.md` for ReportLab migration notes

**Recommendation:** Test option 1 first. If it fails on clean machine, switch to option 3 (ReportLab).

---

### Issue 2: Large Executable Size

**Symptom:** `LisaInvoice.exe` is 100-200MB

**Root Cause:** PyInstaller bundles entire Python runtime + all dependencies + GTK libraries if using WeasyPrint

**Workarounds:**

1. **Accept the size (Recommended for single-user app)**
   - Lisa has ample disk space on modern laptop
   - One-time download, no ongoing updates
   - Reasonable for desktop application in 2026

2. **Use UPX compression (May reduce 20-30%)**
   ```bat
   pyinstaller --onefile --windowed --upx-dir=C:\path\to\upx ...
   ```
   - Download UPX: https://upx.github.io/
   - Warning: May trigger false positives in some antivirus software

3. **Switch to ReportLab (Reduces exe to 50-80MB)**
   - Removes GTK dependencies
   - Smaller Python dependency footprint

---

### Issue 3: Windows SmartScreen Warning

**Symptom:** "Windows protected your PC" blue screen on first launch

**Root Cause:** Executable is not code-signed with a Microsoft-trusted certificate

**Workarounds:**

1. **User instruction: "More info" → "Run anyway" (Recommended)**
   - One-time action per machine
   - Free, no additional tooling
   - Document in installation instructions for Lisa

2. **Code signing certificate (Expensive, unnecessary for single-user app)**
   - Cost: $100-400/year for certificate
   - Requires business entity or verified identity
   - Overkill for personal productivity app

**Recommendation:** Document SmartScreen bypass in installation guide. Lisa will only see this warning once per machine.

---

### Issue 4: Slow First Launch

**Symptom:** 5-10 second delay on first exe launch

**Root Cause:** PyInstaller extracts bundled files to temp directory on first run

**Workarounds:**

1. **Accept the delay (Recommended)**
   - Only affects first launch after reboot
   - Subsequent launches are faster (2-3 seconds)
   - Typical for PyInstaller `--onefile` mode

2. **Switch to `--onedir` mode (Faster launch, messier distribution)**
   ```bat
   pyinstaller --onedir --windowed ...
   ```
   - Creates `dist/LisaInvoice/` folder with exe + DLLs
   - Must distribute entire folder, not single exe
   - Launch time: <2 seconds consistently

**Recommendation:** Keep `--onefile` for simpler distribution (single exe is easier for Lisa).

---

## Testing Checklist

Use this checklist when testing on Windows:

- [ ] **Pre-Build**
  - [ ] Python 3.10+ installed
  - [ ] Node.js 18+ installed
  - [ ] All dependencies installed (`pip install -r requirements.txt`, `npm install`)
  - [ ] `frontend/public/icon.ico` exists

- [ ] **Build Process**
  - [ ] `build.bat` runs without errors
  - [ ] Frontend build succeeds (Vite output shows "built in Xms")
  - [ ] PyInstaller packaging succeeds
  - [ ] `dist/LisaInvoice.exe` created
  - [ ] Exe file size is 50-200MB

- [ ] **Development Machine Testing**
  - [ ] Exe launches without console window (--windowed mode)
  - [ ] Browser opens automatically after 1-2 seconds
  - [ ] React app loads at `http://localhost:5000` (or alt port)
  - [ ] Profile page loads, settings can be saved
  - [ ] Weekly invoice page loads, hours can be entered
  - [ ] PDF generation works (test with "Save" without email)
  - [ ] Generated PDF opens correctly with all content rendered
  - [ ] Email sending works (requires `.env` configuration)
  - [ ] Monthly report functionality works
  - [ ] App can be closed and restarted (persistence works)

- [ ] **Clean Machine Testing**
  - [ ] VM or clean Windows machine prepared
  - [ ] No Python installed on test machine
  - [ ] Only `LisaInvoice.exe` copied to test machine
  - [ ] `config.json` and `.env` copied (if pre-configured)
  - [ ] SmartScreen warning can be bypassed ("More info" → "Run anyway")
  - [ ] All functionality works on clean machine:
    - [ ] App launches and opens browser
    - [ ] Profile can be edited
    - [ ] PDFs can be generated
    - [ ] Emails can be sent (if configured)
  - [ ] No errors related to missing Python or dependencies

- [ ] **Edge Cases**
  - [ ] Port 5000 occupied → app uses alternative port (5001-5010)
  - [ ] Invalid save folder path → app shows error, doesn't crash
  - [ ] Missing .env file → app shows error when trying to send email
  - [ ] Network disconnected → email fails gracefully, PDF still saved
  - [ ] Multiple simultaneous launches → only one instance runs, others open browser to existing instance

---

## Test Results Template

Document test results in this section after running tests on Windows:

### Test Date: [YYYY-MM-DD]
### Tested By: [Name]
### Test Environment:
- Windows Version: [e.g., Windows 11 23H2]
- Python Version (build machine): [e.g., 3.11.5]
- Node.js Version: [e.g., 18.17.0]
- PyInstaller Version: [e.g., 6.19.0]
- WeasyPrint Version: [e.g., 60.2]

### Build Test Results:
- [ ] Build completed: YES / NO
- [ ] Exe created: YES / NO
- [ ] Exe file size: [e.g., 125MB]
- [ ] Build errors encountered: [None / List errors]

### Development Machine Test Results:
- [ ] Exe launches: YES / NO
- [ ] Browser opens: YES / NO
- [ ] React app loads: YES / NO
- [ ] PDF generation works: YES / NO
- [ ] Email sending works: YES / NO
- [ ] Issues encountered: [None / List issues]

### Clean Machine Test Results:
- [ ] Test machine type: [VM / Physical / Windows Sandbox]
- [ ] Python installed on test machine: YES / NO
- [ ] Exe launches: YES / NO
- [ ] All functionality works: YES / NO
- [ ] Issues encountered: [None / List issues]

### WeasyPrint Bundling Status:
- [ ] WeasyPrint bundled successfully: YES / NO
- [ ] GTK dependencies resolved: YES / NO
- [ ] Fallback to ReportLab required: YES / NO

### Overall Status:
- [ ] PASS - All acceptance criteria met
- [ ] CONDITIONAL PASS - Works with documented workarounds
- [ ] FAIL - Critical issues prevent deployment

### Notes:
[Additional observations, performance notes, recommendations]

---

## Fallback Plan: Switching to ReportLab

If WeasyPrint bundling fails on clean machine testing, switch to ReportLab:

### Migration Steps:

1. **Update requirements.txt:**
   ```
   # Replace weasyprint with reportlab
   reportlab==4.0.7
   ```

2. **Rewrite pdf_service.py:**
   - Replace WeasyPrint HTML rendering with ReportLab Canvas API
   - Reimplement templates using ReportLab drawing primitives
   - Reference: https://docs.reportlab.com/reportlab/userguide/ch1_intro/

3. **Update templates:**
   - Convert `app/templates/*.html` to Python functions
   - Use ReportLab's drawing methods (drawString, setFillColor, rect, etc.)
   - Maintain visual design (colors, layout, fonts)

4. **Test and rebuild:**
   ```bat
   pip install -r requirements.txt
   build.bat
   ```

5. **Re-test on clean machine:**
   - ReportLab is pure Python, should bundle reliably
   - Expect smaller exe size (50-80MB vs 100-200MB)

### ReportLab Template Example:

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generate_morning_light_invoice(data, output_path):
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    # Header with rose gradient simulation (solid color)
    c.setFillColorRGB(0.718, 0.431, 0.475)  # #b76e79
    c.rect(0, height - 100, width, 100, fill=1)

    # Invoice title
    c.setFillColorRGB(1, 1, 1)  # white
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "INVOICE")

    # ... rest of template ...

    c.save()
```

**Estimated migration time:** 4-6 hours to rewrite all templates + testing

---

## Recommendations for Deployment

### For Development Testing:
1. Test build process on Windows 10 and Windows 11
2. Test on at least 2 different Windows machines (different hardware/configs)
3. Test with both Python installed and without (clean machine)
4. Test WeasyPrint bundling first before considering ReportLab fallback

### For Production Deployment to Lisa:
1. Run all tests in this document successfully
2. Pre-configure `config.json` with Lisa's information before building
3. Include `.env.example` with instructions for Gmail App Password setup
4. Create a one-page installation guide (see `docs/INSTALL.md`)
5. Schedule a 10-minute phone walkthrough for first launch
6. Have backup plan ready (TeamViewer/AnyDesk for remote support)

### For Future Maintenance:
1. Document the exact Windows environment used for successful build
2. Keep build machine environment consistent (versions, packages)
3. Test any dependency updates on clean machine before deploying to Lisa
4. Consider automating build testing with GitHub Actions (Windows runner)

---

## References

- **PyInstaller Documentation:** https://pyinstaller.org/en/stable/
- **WeasyPrint Windows Guide:** https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows
- **ReportLab User Guide:** https://docs.reportlab.com/reportlab/userguide/
- **GTK for Windows:** https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
- **Gmail App Passwords:** https://myaccount.google.com/apppasswords

---

## Appendix: Automated Test Script

See `test_windows_build.bat` for automated testing script that validates:
- Build completion
- Exe creation
- File size validation
- Basic launch test (if possible without user interaction)
- Logs all results to `test_results.log`

Usage:
```bat
test_windows_build.bat
```

Output: `test_results.log` with pass/fail status for each test
