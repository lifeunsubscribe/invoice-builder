# Clean Machine Testing Procedure

**Originally written:** 2026-03-26
**Last reviewed:** 2026-04-11
**Purpose:** Validate that `Invoice Builder.exe` runs on a Windows machine without Python installed
**Acceptance Criterion:** Exe works on a clean Windows machine or issues are documented with workarounds

> **Status note (2026-04-11):** Most of this procedure predates the GitHub Actions build pipeline and the in-app email setup modal. Several literal references have been updated, but the original spec was written when:
> - The exe was named `LisaInvoice.exe` (now `Invoice Builder.exe`)
> - The default port was 5000 (now 5001)
> - SMTP credentials were hand-edited into a `.env` file next to the exe (now: stored in `{saveFolder}/.env` and managed via the in-app "Set up email" modal which posts to `/api/email-config`)
> - `config.json` was assumed to live in the exe's directory (now: lives at `{saveFolder}/config.json`, with a `pointer.json` in `%APPDATA%\.invoicebuilder\` so the exe can find the save folder)
> - There was no auto-update mechanism (now: in-app self-update via GitHub Releases, polled every 2 hours)
>
> Treat any contradiction in this doc as the doc being out of date relative to the code, not the other way around.

---

## Overview

This document provides a step-by-step procedure for testing Invoice Builder.exe on a "clean" Windows machine - a computer that has never had Python or developer tools installed. This simulates the actual end-user environment (Lisa's laptop) and validates that the PyInstaller bundle is truly self-contained.

---

## Test Machine Requirements

### Minimum System Requirements
- **OS:** Windows 10 (version 1809 or later) or Windows 11
- **RAM:** 4GB minimum, 8GB recommended
- **Disk Space:** 500MB free (200MB for exe + 300MB for generated files)
- **Browser:** Any modern browser (Chrome, Edge, Firefox) - pre-installed on Windows
- **Network:** Internet connection (for email sending test only)

### "Clean" Machine Definition

A clean machine MUST NOT have:
- Python installed (any version)
- Developer tools (Visual Studio, VS Code, Git, etc.)
- PyCharm, Anaconda, or other Python distributions
- GTK or Cairo libraries installed separately

A clean machine MAY have:
- Standard Windows applications (Office, browsers, etc.)
- Antivirus software
- VPN clients
- Other productivity software

---

## Setup Options

Choose one of the following clean machine setups:

### Option A: Windows Virtual Machine (Recommended)

**Best for:** Repeatable testing, easy to reset

**Setup Steps:**
1. Download a free Windows 10/11 development VM:
   - Microsoft: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines/
   - Choose "VMWare", "Hyper-V", "VirtualBox", or "Parallels" depending on your hypervisor
2. Import the VM into your virtualization software
3. Start the VM and complete Windows setup
4. Take a snapshot named "Clean Windows" for easy reset
5. Update Windows (optional but recommended)

**Pros:**
- Free and legal (90-day license, renewable)
- Easy to reset to clean state
- Can run on the same physical machine as development
- Repeatable testing environment

**Cons:**
- Requires ~20GB disk space
- Performance depends on host machine resources

---

### Option B: Windows Sandbox (Quick Testing Only)

**Best for:** Quick validation, not full testing

**Setup Steps:**
1. Check Windows version: Windows 10 Pro/Enterprise/Education or Windows 11 Pro/Enterprise
2. Enable Windows Sandbox:
   - Open "Turn Windows features on or off"
   - Check "Windows Sandbox"
   - Restart computer
3. Launch Windows Sandbox from Start menu
4. Copy files into Sandbox desktop

**Pros:**
- Built into Windows 10/11 Pro+
- Instant setup (no download)
- Automatically clean on every launch
- Lightweight

**Cons:**
- Only available on Pro/Enterprise/Education editions
- Sandbox resets on close (can't test persistence)
- Limited to basic validation
- Cannot test across reboots

**Limitations for this test:**
- ❌ Cannot test config.json persistence across sessions
- ❌ Cannot test exe behavior after reboot
- ✓ Can test basic launch and PDF generation
- ✓ Can test WeasyPrint bundling

---

### Option C: Physical Clean Machine

**Best for:** Final validation before deployment

**Setup Steps:**
1. Identify a Windows computer that has never had Python installed
2. Verify no Python in PATH: Open PowerShell, run `python --version` (should fail)
3. Verify no Python in Programs: Check "Apps & features" for Python
4. If Python exists, this is NOT a clean machine (use Option A or B)

**Pros:**
- Most realistic test environment
- Real hardware performance
- Identical to Lisa's end-user experience

**Cons:**
- Requires access to separate physical machine
- Cannot easily reset to clean state
- May have unpredictable software configurations

**When to use:**
- After VM testing succeeds
- Before final deployment to Lisa
- For performance benchmarking on target hardware

---

## Pre-Test Preparation

### 1. Prepare Test Files

On your development machine, gather the following files:

```
LisaInvoiceTest/
├── Invoice Builder.exe           ← Copy from dist/ after successful build
├── config.example.json       ← Copy from project root (optional)
├── .env.example             ← Copy from project root (optional)
└── README_TEST.txt          ← Create with test instructions
```

**config.example.json** (optional, for pre-configuration — drop this inside the save folder, not next to the exe):
```json
{
  "name": "Test User",
  "address": "123 Test St, Test City, ST 12345",
  "personalEmail": "test@example.com",
  "rate": 28.00,
  "clientName": "Test Client Agency",
  "clientEmail": "client@example.com",
  "accountantEmail": "accountant@example.com",
  "template": "morning-light",
  "accent": "#c47a86",
  "invoiceNote": "Thank you for your business.",
  "saveFolder": "C:\\Users\\Public\\Documents\\test-invoices",
  "occupation": "home-health-aide",
  "agency": "",
  "logSections": ["Food", "Activities", "Travel", "Visitors", "Comments"],
  "enabledVitals": ["temperature", "bpSystolic", "bpDiastolic", "weight", "pulse", "o2sat"],
  "signatureFont": "",
  "clients": [
    {
      "id": "client-1",
      "name": "Test Patient",
      "address": "456 Patient Ave",
      "objective": "Care plan goals",
      "meds": [],
      "defaultShift": {"start": "09:00", "end": "17:00"}
    }
  ],
  "activeClientId": "client-1"
}
```

**README_TEST.txt:**
```
Invoice Builder - Test Instructions

1. Double-click Invoice Builder.exe to launch
2. If Windows SmartScreen appears:
   - Click "More info"
   - Click "Run anyway"
3. Wait for browser to open (may take 5-10 seconds first time)
4. Application should open at http://localhost:5001

For testing with email:
- Use the in-app "Set up email" button (top-right corner)
- Enter your Gmail address and a Gmail app password
- Gmail app password: https://myaccount.google.com/apppasswords
- This writes a .env file to {saveFolder}/.env automatically

For testing with pre-filled profile:
- Place config.json inside the save folder (e.g. C:\Users\Public\Documents\test-invoices\config.json)
- The app discovers it via a pointer file in %APPDATA%\.invoicebuilder\pointer.json
```

### 2. Transfer Files to Test Machine

**For VM/Sandbox:**
- **VMware/VirtualBox:** Use shared folders or drag-and-drop
- **Hyper-V:** Use Enhanced Session or network share
- **Windows Sandbox:** Simply drag files into Sandbox window

**For Physical Machine:**
- USB flash drive (simplest)
- Network share
- Cloud storage (Dropbox, Google Drive, OneDrive)
- Email attachment (if exe < 25MB)

### 3. Verify Clean State

Before testing, verify the test machine is truly clean:

**Open PowerShell on test machine and run:**
```powershell
# Check Python is NOT installed
python --version
# Expected: 'python' is not recognized...

# Check pip is NOT installed
pip --version
# Expected: 'pip' is not recognized...

# Check no Python in PATH
$env:PATH -split ';' | Select-String -Pattern 'python'
# Expected: No output

# Check Programs and Features
Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like '*Python*' }
# Expected: No output
```

If any of these commands succeed or return Python-related paths, the machine is NOT clean.

---

## Test Procedure

### Test 1: Initial Launch

**Objective:** Verify exe launches and opens browser without errors

**Steps:**
1. Navigate to folder containing `Invoice Builder.exe`
2. Double-click `Invoice Builder.exe`
3. Observe Windows SmartScreen warning (expected first time)
4. Click "More info" → "Run anyway"
5. Wait 5-10 seconds
6. Observe browser opening automatically

**Expected Results:**
- ✓ No error dialog appears
- ✓ No console window appears (windowed mode)
- ✓ Default browser opens to `http://localhost:5001`
- ✓ React app loads showing "Invoice Builder" interface
- ✓ Landing page displays with three menu options:
  - Weekly Invoice
  - Monthly Report
  - Edit Profile

**Possible Issues:**

| Issue | Cause | Solution |
|-------|-------|----------|
| "Windows protected your PC" dialog | Unsigned exe (expected) | Click "More info" → "Run anyway" |
| Console window appears | Build used wrong flag | Rebuild with `--windowed` flag |
| Browser doesn't open | Port 5000 occupied | Check app console (if visible) for alt port |
| "Static files not found" error | Bundling failed | Rebuild with correct `--add-data` flag |
| Browser shows blank page | Frontend not bundled | Check browser console (F12), rebuild |

**Test Result:** ☐ PASS ☐ FAIL

**Notes:**
```
[Record any observations, timing, or issues]
```

---

### Test 2: Profile Configuration

**Objective:** Verify app can read and write config.json

**Steps:**
1. From Landing page, click "Edit Profile"
2. Enter test data:
   - Name: "Test User"
   - Address: "123 Test St"
   - Personal Email: "test@example.com"
   - Rate: 28.00
   - Client Name: "Test Agency"
   - Client Email: "client@example.com"
   - Accountant Email: "accountant@example.com"
3. Observe "Save Folder" auto-derived path
4. Click "Save Profile"
5. Navigate back to Landing page
6. Return to Edit Profile
7. Verify all fields retained values

**Expected Results:**
- ✓ All fields accept input without errors
- ✓ Save folder auto-derives correctly (e.g., `~/Documents/test-u-invoices`)
- ✓ "Profile saved" confirmation appears
- ✓ Values persist after navigation
- ✓ `config.json` created **inside the save folder** (not next to the exe)
- ✓ A `pointer.json` is written to `%APPDATA%\.invoicebuilder\` so the exe can locate the save folder on next launch

**Possible Issues:**

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot write config.json" | Permission error on save folder | Pick a save folder under `~/Documents/` (or any user-writable path) |
| Save folder path invalid | Windows path parsing | Use backslashes or forward slashes consistently |
| Data doesn't persist | `pointer.json` missing from `%APPDATA%\.invoicebuilder\` | Re-save profile; verify the pointer file gets created |
| Old config.json next to exe is being read | Pre-multi-client behavior | Delete the stray exe-adjacent `config.json` — the canonical location is `{saveFolder}/config.json` |

**Verification:**
- Open File Explorer
- Navigate to the save folder shown in the Profile (e.g., `C:\Users\<user>\Documents\test-u-invoices\`)
- Verify `config.json` exists there
- Open `config.json` in Notepad, verify contents match entered data
- Verify `%APPDATA%\.invoicebuilder\pointer.json` exists and points at the save folder

**Test Result:** ☐ PASS ☐ FAIL

**Notes:**
```
[Record config.json location and contents]
```

---

### Test 3: Weekly Invoice Creation (No Email)

**Objective:** Verify PDF generation works in bundled exe

**Steps:**
1. From Landing page, click "Weekly Invoice"
2. Observe current week pre-selected
3. Enter test hours:
   - Monday: 8
   - Tuesday: 8
   - Wednesday: 8
   - Thursday: 8
   - Friday: 8
4. Observe PDF preview updates in real-time
5. Observe totals: 40 hours, $1120.00 (if rate = 28)
6. Click template dropdown, try different templates
7. Return to "Morning Light" template
8. Do NOT send email yet - focus on PDF generation
9. Check if app offers "Save without sending" option, or:
10. Configure a fake client email (e.g., "test@localhost.local")
11. Click "Save & Submit"
12. Observe save location in success message

**Expected Results:**
- ✓ Hours can be entered in all day fields
- ✓ PDF preview renders correctly (may have "preview" watermark)
- ✓ Totals calculate correctly
- ✓ Template switching works
- ✓ PDF saved to configured folder: `{saveFolder}/weekly/INV-YYYYMMDD.pdf`
- ✓ Success notification appears
- ✓ No WeasyPrint/GTK errors

**CRITICAL: WeasyPrint Bundling Validation**

If any of these errors appear, WeasyPrint bundling has FAILED:

```
OSError: cannot load library 'gobject-2.0-0'
OSError: cannot load library 'cairo-2'
OSError: cannot load library 'pango-1.0-0'
ImportError: No module named 'cairocffi'
```

**If WeasyPrint fails:**
1. Document exact error message
2. Check if GTK is installed on test machine (should NOT be)
3. Return to development machine
4. Follow "Fallback Plan: Switching to ReportLab" in PACKAGING_NOTES.md
5. Rebuild and re-test

**Verification:**
- Navigate to save folder (e.g., `C:\Users\Public\Documents\test-u-invoices\weekly\`)
- Verify `INV-YYYYMMDD.pdf` exists (date = Monday of test week)
- Double-click PDF, verify it opens in default PDF viewer
- Verify PDF contents:
  - ✓ Correct template styling (colors, layout)
  - ✓ All hours displayed correctly
  - ✓ Totals match (40 hours, $1120.00)
  - ✓ Name and address from profile
  - ✓ No garbled text or broken fonts
  - ✓ Client name displayed

**Test Result:** ☐ PASS ☐ FAIL

**Notes:**
```
[Record PDF save location, file size, any rendering issues]
```

---

### Test 4: Email Sending (Optional)

**Objective:** Verify email functionality works from bundled exe

**Prerequisites:**
- Gmail account with App Password generated (https://myaccount.google.com/apppasswords, requires 2FA)
- Save folder configured in Profile (Test 2)
- Valid recipient email addresses in `config.json`

**Steps:**
1. In the top-right corner of the app, click the **"Set up email"** button (yellow). This opens a modal that posts to `POST /api/email-config` and writes `{saveFolder}/.env` with `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD`.
2. Enter the Gmail address and App Password, click Save.
3. Confirm the button now shows the green check mark (`emailConfigured === true`).
4. From Weekly Invoice page, enter test hours.
5. Click "Save & Submit".
6. Observe "Sending email..." status.
7. Wait for success notification.
8. Check Gmail "Sent" folder.
9. Check recipient inbox (if using your own email).
10. Verify email contents and attachment.

**Expected Results:**
- ✓ "Set up email" modal saves credentials successfully (no error)
- ✓ `{saveFolder}/.env` file exists with `GMAIL_ADDRESS=` and `GMAIL_APP_PASSWORD=` lines
- ✓ No SMTP connection errors
- ✓ No authentication errors
- ✓ Success notification: "Invoice saved and sent!"
- ✓ Email appears in Gmail Sent folder
- ✓ Email received at client and accountant addresses
- ✓ Email body contains week dates and totals
- ✓ PDF attached correctly
- ✓ PDF attachment can be opened from email

**Possible Issues:**

| Issue | Cause | Solution |
|-------|-------|----------|
| "SMTP authentication failed" (535) | Wrong password or not using App Password | Generate App Password at https://myaccount.google.com/apppasswords |
| "SMTP connection failed" (timeout) | Firewall/network blocking port 587 | Check firewall, try different network |
| "GMAIL_ADDRESS not found in .env" | `.env` is in the wrong location (e.g. next to exe instead of save folder) | Move it to `{saveFolder}/.env`, or re-run the "Set up email" modal |
| Email sent but no attachment | PDF generation failed silently | Check Test 3 first |
| Email in Spam | Expected for test accounts | Check recipient Spam folder |

**Test Result:** ☐ PASS ☐ FAIL ☐ SKIPPED (no email config)

**Notes:**
```
[Record email delivery time, any SMTP errors]
```

---

### Test 5: Monthly Report Functionality

**Objective:** Verify monthly report generation and scan functionality

**Prerequisites:**
- At least one weekly invoice saved (from Test 3)

**Steps:**
1. From Landing page, click "Monthly Report"
2. Observe "Scanning for invoices..." popup
3. Wait for scan to complete
4. Observe scanned weeks populate in report
5. Verify hours pre-filled from saved invoices
6. Click "Save & Submit" (or save without sending)
7. Verify monthly PDF created

**Expected Results:**
- ✓ Scan popup appears and completes
- ✓ Previously saved weekly invoices detected
- ✓ Hours auto-populated from sidecar JSON files
- ✓ Monthly report table displays correctly
- ✓ Monthly PDF saved to `{saveFolder}/monthly/RPT-YYYY-MM.pdf`
- ✓ Monthly PDF has different layout from weekly (accountant-oriented)

**Verification:**
- Navigate to `{saveFolder}/monthly/`
- Verify `RPT-YYYY-MM.pdf` exists
- Open PDF, verify:
  - ✓ Month and year correct
  - ✓ Week-by-week table
  - ✓ Hours match saved weekly invoices
  - ✓ Total hours calculated correctly
  - ✓ Signature line present

**Test Result:** ☐ PASS ☐ FAIL

**Notes:**
```
[Record scan results, monthly PDF details]
```

---

### Test 6: Application Restart & Persistence

**Objective:** Verify config persists across app restarts

**Steps:**
1. Close browser tab
2. Close application (if console visible, or just close browser)
3. Wait 5 seconds
4. Launch `Invoice Builder.exe` again
5. Verify browser opens to app
6. Navigate to Edit Profile
7. Verify all previously entered data still present
8. Navigate to Weekly Invoice
9. Check "Saving to" pill shows correct folder
10. Navigate to weekly invoice folder (if PDFs saved earlier)
11. Verify PDFs still accessible

**Expected Results:**
- ✓ App launches successfully on second run (faster than first)
- ✓ All config.json data persists
- ✓ Previously saved PDFs still accessible
- ✓ No data loss

**Test Result:** ☐ PASS ☐ FAIL

**Notes:**
```
[Record any persistence issues]
```

---

### Test 7: Error Handling & Edge Cases

**Objective:** Verify graceful error handling

**Test 7A: Invalid Save Folder**
1. Edit Profile → Save Folder: `Z:\NonexistentDrive\folder`
2. Try to save a weekly invoice
3. Verify user-friendly error message (not crash)

**Expected:** ✓ Error notification, app doesn't crash

**Test 7B: Missing .env File (Email Test)**
1. Rename or delete `.env` file
2. Try to send a weekly invoice
3. Verify error message about missing credentials

**Expected:** ✓ Error about email configuration, PDF still saved locally

**Test 7C: Port 5001 Already Occupied**
1. Keep app running
2. Launch `Invoice Builder.exe` again (second instance)
3. Verify behavior

**Expected:**
- ✓ Second instance detects first is running on 5001 via `is_this_app_running_on_port()`
- ✓ Second instance opens browser to existing app and exits gracefully
- ✓ OR (if port 5001 is occupied by something else): second instance uses port 5002-5010

**Test 7D: Invalid Email Address**
1. Edit Profile → Client Email: `not-an-email`
2. Try to send invoice
3. Verify validation error

**Expected:** ✓ User-friendly validation message

**Test Result:** ☐ PASS ☐ FAIL

**Notes:**
```
[Record error handling behavior]
```

---

## Clean Machine Test Checklist

Use this checklist to ensure all tests completed:

### Pre-Test Validation
- [ ] Test machine has NO Python installed (verified with `python --version`)
- [ ] Test machine is Windows 10/11
- [ ] Test files copied to test machine (exe + optional config/env)
- [ ] Test machine has internet connection (for email test)

### Core Functionality Tests
- [ ] Test 1: Initial Launch - PASS / FAIL
- [ ] Test 2: Profile Configuration - PASS / FAIL
- [ ] Test 3: PDF Generation - PASS / FAIL
- [ ] Test 4: Email Sending - PASS / FAIL / SKIPPED
- [ ] Test 5: Monthly Reports - PASS / FAIL
- [ ] Test 6: Persistence - PASS / FAIL
- [ ] Test 7: Error Handling - PASS / FAIL

### Critical Validations
- [ ] WeasyPrint bundled successfully (no GTK errors)
- [ ] PDFs render correctly (fonts, colors, layout)
- [ ] No crashes or unhandled exceptions
- [ ] No Python-related error messages
- [ ] Application is truly standalone

### Documentation
- [ ] All test results recorded in this document
- [ ] Issues/failures documented in PACKAGING_NOTES.md
- [ ] Screenshots captured (optional but helpful)
- [ ] exe file size recorded
- [ ] Windows version recorded

---

## Test Results Summary

**Test Date:** _______________
**Tested By:** _______________
**Test Machine:** ☐ VM ☐ Windows Sandbox ☐ Physical Machine
**Windows Version:** _______________
**Exe File Size:** _______________ MB

### Overall Results:
- **Total Tests:** _____
- **Passed:** _____
- **Failed:** _____
- **Skipped:** _____

### Critical Issues Found:
```
[List any blocking issues, e.g., "WeasyPrint GTK error", "PDF rendering broken", etc.]
```

### Non-Critical Issues Found:
```
[List minor issues, e.g., "Slow first launch", "SmartScreen warning", etc.]
```

### Recommendations:
```
[e.g., "Ready for deployment", "Switch to ReportLab fallback", "Fix X before deployment"]
```

---

## Acceptance Criteria Verification

Per task requirements, verify:

- [ ] **build.bat completes without errors on Windows** (from test_windows_build.bat)
- [ ] **Invoice Builder.exe created in dist/** (from test_windows_build.bat)
- [ ] **Exe launches and opens browser** (Test 1)
- [ ] **PDF generation works from bundled exe** (Test 3)
- [ ] **Email sending works from bundled exe** (Test 4, if .env provided)
- [ ] **Clean machine test passes (no Python installed)** (All tests)
- [ ] **PACKAGING_NOTES.md documents any issues/workarounds** (created)

### Final Status:
☐ **PASS** - All acceptance criteria met, ready for deployment
☐ **CONDITIONAL PASS** - Works with documented workarounds
☐ **FAIL** - Critical issues require fixes before deployment

---

## Next Steps After Clean Machine Test

### If All Tests Pass:
1. Document results in PACKAGING_NOTES.md (Test Results Template section)
2. Mark issue #22 as complete
3. Prepare deployment to Lisa:
   - Pre-configure config.json with Lisa's data
   - Create installation guide
   - Schedule walkthrough call
4. Optional: Test on Lisa's actual hardware before final deployment

### If Tests Fail Due to WeasyPrint:
1. Document exact error messages
2. Follow "Fallback Plan: Switching to ReportLab" in PACKAGING_NOTES.md
3. Rebuild with ReportLab
4. Re-run this entire clean machine test procedure
5. Update PACKAGING_NOTES.md with ReportLab results

### If Tests Fail Due to Other Issues:
1. Document issues in detail (error messages, screenshots)
2. Log to scratchpad: `YYYY-MM-DD | file:line | category | description`
3. Determine if issues are blocking or can be worked around
4. Fix critical issues and re-test
5. Update PACKAGING_NOTES.md with findings

---

## Troubleshooting Quick Reference

### "Cannot load library 'gobject-2.0-0'"
- **Cause:** WeasyPrint GTK bundling failed
- **Solution:** Switch to ReportLab fallback (see PACKAGING_NOTES.md)

### "Static files not found" (legacy — should not happen as of 2026-04-11)
- **Cause:** Frontend dist not bundled correctly. Vite builds to project-root `dist/`, so the PyInstaller arg should be `--add-data "dist;dist"` (matching `.github/workflows/build.yml`). The legacy `build.bat` uses `--add-data "frontend/dist;dist"` which is incorrect — Vite's `outDir` is `../dist`.
- **Current behavior:** the exe will exit immediately with code 2 instead of serving a JSON 500. CI's smoke test (`Verify exe starts and serves frontend`) catches this before release.

### "SMTP authentication failed"
- **Cause:** Using regular password instead of App Password
- **Solution:** Generate Gmail App Password

### "Port 5001 occupied"
- **Expected:** App auto-detects and uses port 5002-5010
- **Verify:** Check console output for actual port

### "Windows protected your PC"
- **Expected:** Unsigned exe triggers SmartScreen
- **Solution:** "More info" → "Run anyway" (one-time only)

### Blank browser page
- **Cause:** Frontend build failed or not bundled
- **Solution:** Check browser console (F12), rebuild frontend

---

## Appendix: Test Automation

For repetitive testing (e.g., after rebuilds), consider:

1. **Automated VM snapshots:**
   - Create "Clean Windows" snapshot
   - Test
   - Revert to snapshot
   - Repeat

2. **PowerShell test script** (partial automation):
   ```powershell
   # Launch app
   Start-Process "Invoice Builder.exe"

   # Wait for browser
   Start-Sleep -Seconds 10

   # Check if port 5000 is listening
   Test-NetConnection -ComputerName localhost -Port 5000

   # Open browser (if not auto-opened)
   Start-Process "http://localhost:5001"
   ```

3. **Selenium/Playwright** (advanced):
   - Automate browser interactions
   - Validate UI elements
   - Test PDF generation
   - Capture screenshots

---

**Document Version:** 1.0
**Last Updated:** 2026-03-26
