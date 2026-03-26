# Development Scratchpad

This file tracks issues encountered during development that are outside the current issue scope.

## Encountered Issues (Needs Triage)

- **2026-03-26** | `build.bat:23-27` | code-smell | PyInstaller build command does not include WeasyPrint bundling flags (--collect-all weasyprint --collect-all cairocffi --collect-all tinycss2) | Affects: Windows executable bundling, PDF generation may fail on clean machines due to missing GTK dependencies | Fix: Add WeasyPrint collection flags to build.bat PyInstaller command as documented in docs/PACKAGING_NOTES.md lines 314-323 | Status: Documented as Issue 1 workaround in PACKAGING_NOTES.md - awaiting Windows testing to determine if flags are required
