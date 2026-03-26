"""
WeasyPrint + PyInstaller Bundling Spike

This script tests whether WeasyPrint can be successfully bundled with PyInstaller
to create a standalone Windows executable without requiring GTK installation.

Test objectives:
1. Generate a simple PDF using WeasyPrint
2. Verify the PDF renders correctly with basic HTML/CSS
3. Test that this script can be packaged with PyInstaller --onefile
4. Confirm the resulting .exe runs on a clean Windows machine without Python

Usage:
  python weasyprint_test.py

Expected output:
  - test_invoice.pdf created in current directory
  - Console message confirming success
  - No GTK-related errors

PyInstaller build command to test:
  pyinstaller --onefile --name=WeasyPrintTest weasyprint_test.py

Note: If bundling fails due to GTK dependencies, we will fall back to ReportLab
as documented in the ADR (Invoice-Builder-ADR.md, PDF Generation section).
"""

import sys
from datetime import datetime
from pathlib import Path

try:
    from weasyprint import HTML, CSS
except ImportError:
    print("ERROR: WeasyPrint is not installed.")
    print("Install with: pip install weasyprint")
    sys.exit(1)


def create_test_invoice():
    """Generate a test invoice PDF to verify WeasyPrint functionality."""

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Test Invoice</title>
        <style>
            @page {
                size: letter;
                margin: 1in;
            }
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #333;
                line-height: 1.6;
            }
            .header {
                background: linear-gradient(135deg, #f5e6e8 0%, #fdf5f0 100%);
                padding: 30px;
                margin-bottom: 30px;
                border-radius: 8px;
            }
            .header h1 {
                color: #b76e79;
                margin: 0 0 10px 0;
                font-size: 28px;
            }
            .invoice-details {
                margin-bottom: 30px;
            }
            .invoice-details p {
                margin: 5px 0;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 30px;
            }
            th {
                background-color: #b76e79;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }
            td {
                padding: 10px 12px;
                border-bottom: 1px solid #e0e0e0;
            }
            .total-row {
                font-weight: bold;
                background-color: #f9f9f9;
            }
            .footer {
                margin-top: 40px;
                padding-top: 20px;
                border-top: 2px solid #b76e79;
                text-align: center;
                color: #666;
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Weekly Invoice - TEST</h1>
            <p><strong>Test User</strong></p>
            <p>123 Test Street, Test City, TS 12345</p>
        </div>

        <div class="invoice-details">
            <p><strong>Invoice Number:</strong> INV-TEST-001</p>
            <p><strong>Date:</strong> """ + datetime.now().strftime("%B %d, %Y") + """</p>
            <p><strong>Week:</strong> Test Week</p>
            <p><strong>Bill To:</strong> Test Client Agency</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Day</th>
                    <th>Hours</th>
                    <th>Rate</th>
                    <th>Amount</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Monday</td>
                    <td>8.0</td>
                    <td>$28.00</td>
                    <td>$224.00</td>
                </tr>
                <tr>
                    <td>Tuesday</td>
                    <td>8.0</td>
                    <td>$28.00</td>
                    <td>$224.00</td>
                </tr>
                <tr>
                    <td>Wednesday</td>
                    <td>8.0</td>
                    <td>$28.00</td>
                    <td>$224.00</td>
                </tr>
                <tr>
                    <td>Thursday</td>
                    <td>8.0</td>
                    <td>$28.00</td>
                    <td>$224.00</td>
                </tr>
                <tr>
                    <td>Friday</td>
                    <td>8.0</td>
                    <td>$28.00</td>
                    <td>$224.00</td>
                </tr>
                <tr class="total-row">
                    <td colspan="2"><strong>Total</strong></td>
                    <td><strong>40 hours</strong></td>
                    <td><strong>$1,120.00</strong></td>
                </tr>
            </tbody>
        </table>

        <div class="footer">
            <p>Thank you for the privilege of caring for your clients.</p>
            <p>This is a test invoice generated by the WeasyPrint + PyInstaller spike.</p>
        </div>
    </body>
    </html>
    """

    output_path = Path("test_invoice.pdf")

    try:
        # Generate PDF from HTML
        HTML(string=html_content).write_pdf(output_path)
        print(f"✓ SUCCESS: PDF generated successfully")
        print(f"  Output: {output_path.absolute()}")
        print(f"  Size: {output_path.stat().st_size:,} bytes")
        return True
    except Exception as e:
        print(f"✗ FAILED: PDF generation failed")
        print(f"  Error: {type(e).__name__}: {e}")
        return False


def check_weasyprint_version():
    """Display WeasyPrint version and dependencies."""
    import weasyprint
    print(f"WeasyPrint version: {weasyprint.__version__}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print()


def main():
    """Run the spike test."""
    print("=" * 60)
    print("WeasyPrint + PyInstaller Bundling Spike")
    print("=" * 60)
    print()

    check_weasyprint_version()

    print("Testing PDF generation...")
    print()

    success = create_test_invoice()

    print()
    print("=" * 60)
    if success:
        print("SPIKE STATUS: PASS (local test)")
        print()
        print("Next steps:")
        print("1. Build executable: pyinstaller --onefile spike/weasyprint_test.py")
        print("2. Test .exe on clean Windows machine without Python")
        print("3. Document results in docs/SPIKE_RESULTS.md")
    else:
        print("SPIKE STATUS: FAIL")
        print()
        print("Consider fallback to ReportLab (no native dependencies)")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
