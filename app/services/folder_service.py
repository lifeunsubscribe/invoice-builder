"""
Folder service for invoice storage and file system operations.

Handles path generation, folder creation, and sidecar JSON read/write
for weekly/monthly PDFs.
"""

import os
import json
from typing import Optional


def weekly_path(base: str, inv_num: str) -> str:
    """
    Generate the full path for a weekly invoice PDF.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")
        inv_num: Invoice number (e.g., "INV-20260324")

    Returns:
        Full path to the weekly PDF (e.g., "{base}/weekly/INV-20260324.pdf")
    """
    return f"{base}/weekly/{inv_num}.pdf"


def monthly_path(base: str, year: int, month: int) -> str:
    """
    Generate the full path for a monthly report PDF.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")
        year: Year (e.g., 2026)
        month: Month (1-indexed, 1=January, 12=December)

    Returns:
        Full path to the monthly PDF (e.g., "{base}/monthly/RPT-2026-03.pdf")
    """
    # Pad month with zero
    month_str = str(month).zfill(2)
    return f"{base}/monthly/RPT-{year}-{month_str}.pdf"


def ensure_folders(base: str) -> None:
    """
    Create weekly/ and monthly/ subdirectories if they don't exist.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")

    Creates:
        {base}/weekly/
        {base}/monthly/
    """
    weekly_dir = os.path.join(base, "weekly")
    monthly_dir = os.path.join(base, "monthly")

    os.makedirs(weekly_dir, exist_ok=True)
    os.makedirs(monthly_dir, exist_ok=True)


def expand_path(path: str) -> str:
    """
    Expand path with ~ (home directory) support.

    Args:
        path: Path potentially containing ~ (e.g., "~/Documents/invoices")

    Returns:
        Expanded absolute path
    """
    return os.path.expanduser(path)


def write_sidecar(pdf_path: str, data: dict) -> None:
    """
    Write JSON sidecar file alongside a PDF.

    The sidecar file stores metadata (e.g., hours data) for the PDF.

    Args:
        pdf_path: Path to the PDF file (e.g., "/path/to/INV-20260324.pdf")
        data: Dictionary to write as JSON (e.g., {"totalHours": 40, "dailyHours": {...}})

    Creates:
        A .json file with the same base name as the PDF
        (e.g., "/path/to/INV-20260324.json")
    """
    # Replace .pdf extension with .json
    json_path = pdf_path.rsplit('.pdf', 1)[0] + '.json'

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_sidecar(pdf_path: str) -> Optional[dict]:
    """
    Read JSON sidecar file for a PDF.

    Args:
        pdf_path: Path to the PDF file (e.g., "/path/to/INV-20260324.pdf")

    Returns:
        Parsed JSON data as a dictionary, or None if the file doesn't exist
        or cannot be parsed
    """
    # Replace .pdf extension with .json
    json_path = pdf_path.rsplit('.pdf', 1)[0] + '.json'

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None
