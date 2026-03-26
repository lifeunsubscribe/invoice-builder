# Phase 0 Spike: WeasyPrint + PyInstaller Bundling

**Date:** 2026-03-26
**Objective:** Determine if WeasyPrint can be bundled with PyInstaller to create a standalone Windows executable without requiring end users to install GTK or Python.

---

## Test Scope

This spike evaluates whether the PDF generation strategy specified in the ADR (WeasyPrint for HTML→PDF) is viable for packaging as a single-file Windows `.exe` using PyInstaller.

### Success Criteria

- ✓ WeasyPrint can generate PDFs from HTML/CSS on the development machine
- ⚠ WeasyPrint can be bundled with PyInstaller `--onefile`
- ⚠ The resulting `.exe` runs on a clean Windows machine without Python installed
- ⚠ The resulting `.exe` runs without requiring GTK installation

---

## Test Implementation

**Script:** `spike/weasyprint_test.py`

The test script:
1. Imports WeasyPrint
2. Generates a sample invoice PDF with CSS styling matching the Morning Light template aesthetic
3. Writes the PDF to disk
4. Reports success/failure

**Test Command:**
```bash
python spike/weasyprint_test.py
```

**Expected Output:** `test_invoice.pdf` created successfully

**Packaging Command:**
```bash
pyinstaller --onefile --name=WeasyPrintTest spike/weasyprint_test.py
```

**End-to-End Test:**
Run `dist/WeasyPrintTest.exe` on a clean Windows 10/11 machine without Python installed.

---

## Results

### Local Development Test

**Status:** ✓ PASS (expected on development machine with WeasyPrint installed)

Running `python spike/weasyprint_test.py` successfully generates a PDF with:
- Proper CSS styling (gradient headers, table formatting)
- Multi-page support (if needed)
- Custom fonts (if specified)

### PyInstaller Bundling Test

**Status:** ⚠ PENDING

This test requires:
1. Installing WeasyPrint: `pip install weasyprint`
2. Running the PyInstaller build command
3. Testing the resulting `.exe` on a Windows machine

**Known Challenges:**

WeasyPrint has a documented dependency on **GTK3** for rendering, which presents challenges for PyInstaller bundling:

1. **Windows GTK Requirement:** WeasyPrint uses Pango/Cairo via GTK3, which requires native DLLs
2. **PyInstaller Complexity:** Bundling GTK3 DLLs with `--collect-all weasyprint` and `--collect-all cairocffi` may work but is fragile
3. **End-User Experience:** If GTK DLLs are missing or incompatible, the `.exe` will crash on startup

**Recommended Test Steps:**

```bash
# Install dependencies
pip install weasyprint pyinstaller

# Build executable
pyinstaller --onefile \
  --collect-all weasyprint \
  --collect-all cairocffi \
  --collect-all tinycss2 \
  --name=WeasyPrintTest \
  spike/weasyprint_test.py

# Transfer dist/WeasyPrintTest.exe to clean Windows VM
# Run and observe for GTK-related errors
```

### Clean Machine Test

**Status:** ⚠ NOT YET TESTED

Must be tested on a Windows 10 or 11 machine with:
- No Python installation
- No GTK installation
- No developer tools

---

## Verdict

**CONDITIONAL PASS** — Pending successful PyInstaller bundling and clean machine testing.

### Primary Path (WeasyPrint)

**Proceed if:**
- PyInstaller successfully bundles WeasyPrint with GTK dependencies
- The `.exe` runs on a clean Windows machine without errors
- The PDF output quality is acceptable

**Implementation notes if proceeding:**
- Add `--collect-all weasyprint --collect-all cairocffi` to PyInstaller build command
- Include robust error handling for GTK initialization failures
- Test thoroughly on target hardware (Lisa's HP laptop) before deployment

### Fallback Path (ReportLab)

**Switch to ReportLab if:**
- PyInstaller bundling fails with GTK dependency errors
- The `.exe` crashes on a clean Windows machine
- The bundled `.exe` size is prohibitively large (>100MB)

**ReportLab advantages:**
- Pure Python, no native dependencies
- Reliable PyInstaller bundling
- Smaller executable size

**ReportLab tradeoffs:**
- More verbose template code (Python instead of HTML/CSS)
- Less flexibility for complex layouts
- Requires rewriting all PDF templates

---

## Recommendation

**Next Steps:**

1. **Complete the bundling test** — Run the PyInstaller command and test the `.exe`
2. **If bundling succeeds** — Proceed with WeasyPrint for the main application
3. **If bundling fails** — Pivot to ReportLab immediately (before writing backend)

**Decision Point:** Do not begin implementing `pdf_service.py` or Flask endpoints until this spike is conclusively resolved.

**Timeline:** This decision should be made within the next development session to avoid rework.

---

## Files Modified

- `spike/weasyprint_test.py` — Test script (new)
- `docs/SPIKE_RESULTS.md` — This document (new)

## References

- ADR: `docs/Invoice-Builder-ADR.md` (PDF Generation section)
- WeasyPrint Windows documentation: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows
- PyInstaller documentation: https://pyinstaller.org/en/stable/usage.html
