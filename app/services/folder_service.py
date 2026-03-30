"""
Folder service for invoice storage and file system operations.

Handles path generation, folder creation, and sidecar JSON read/write
for weekly/monthly PDFs.
"""

import os
import json
from typing import Optional


def validate_safe_path(base: str, target: str) -> None:
    """
    Validate that target path is within base directory to prevent path traversal.

    This function provides defense-in-depth security by ensuring that file
    operations stay within the intended directory structure, even when callers
    are trusted internal components.

    Args:
        base: Base directory path (will be normalized)
        target: Target path to validate (will be normalized)

    Raises:
        ValueError: If target path attempts to escape base directory

    Example:
        >>> validate_safe_path("/home/user/invoices", "/home/user/invoices/weekly/INV-001.pdf")
        # Returns None (valid)

        >>> validate_safe_path("/home/user/invoices", "/etc/passwd")
        # Raises ValueError (path traversal attempt)
    """
    # Resolve both paths to absolute, normalized paths
    # This handles symbolic links, relative paths, and .. components
    base_real = os.path.realpath(os.path.abspath(base))
    target_real = os.path.realpath(os.path.abspath(target))

    # Ensure target is within base (or is base itself)
    # Use os.path.commonpath to handle edge cases properly
    try:
        common = os.path.commonpath([base_real, target_real])
        if common != base_real:
            raise ValueError(
                f"Path traversal detected: target path '{target}' "
                f"is outside base directory '{base}'"
            )
    except ValueError as e:
        # os.path.commonpath raises ValueError if paths are on different drives (Windows)
        # or if one path is relative and the other absolute
        raise ValueError(
            f"Invalid path configuration: cannot validate '{target}' "
            f"against base '{base}': {str(e)}"
        )


def weekly_path(base: str, inv_num: str) -> str:
    """
    Generate the full path for a weekly invoice PDF.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")
        inv_num: Invoice number (e.g., "INV-20260324")

    Returns:
        Full path to the weekly PDF (e.g., "{base}/weekly/INV-20260324.pdf")

    Raises:
        ValueError: If the generated path would escape the base directory
    """
    # Security: Check for path traversal components in inv_num before processing
    # This detects both parent directory references (..) and absolute paths
    if '..' in inv_num or os.path.isabs(inv_num):
        raise ValueError(
            f"Path traversal detected: inv_num '{inv_num}' contains "
            f"invalid path components"
        )

    path = f"{base}/weekly/{inv_num}.pdf"

    # Security: Validate that the constructed path stays within base
    # Defense-in-depth to handle edge cases (symlinks, etc.)
    validate_safe_path(base, path)

    return path


def monthly_path(base: str, year: int, month: int) -> str:
    """
    Generate the full path for a monthly report PDF.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")
        year: Year (e.g., 2026)
        month: Month (1-indexed, 1=January, 12=December)

    Returns:
        Full path to the monthly PDF (e.g., "{base}/monthly/RPT-2026-03.pdf")

    Raises:
        ValueError: If the generated path would escape the base directory
    """
    # Pad month with zero
    month_str = str(month).zfill(2)
    path = f"{base}/monthly/RPT-{year}-{month_str}.pdf"

    # Security: Validate that the constructed path stays within base
    # Defense-in-depth even though year/month are integers
    validate_safe_path(base, path)

    return path


def logs_path(base: str, date_str: str) -> str:
    """
    Generate the full path for a daily service log JSON file.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")
        date_str: Date string in YYYY-MM-DD format (e.g., "2026-03-29")

    Returns:
        Full path to the log JSON (e.g., "{base}/logs/LOG-2026-03-29.json")

    Raises:
        ValueError: If the generated path would escape the base directory
    """
    if '..' in date_str or os.path.isabs(date_str):
        raise ValueError(
            f"Path traversal detected: date_str '{date_str}' contains "
            f"invalid path components"
        )

    path = f"{base}/logs/LOG-{date_str}.json"
    validate_safe_path(base, path)
    return path


def ensure_folders(base: str) -> None:
    """
    Create weekly/, monthly/, and logs/ subdirectories if they don't exist.

    Args:
        base: Base folder path (e.g., "~/Documents/lisa-w-invoices")

    Creates:
        {base}/weekly/
        {base}/monthly/
        {base}/logs/

    Raises:
        ValueError: If subdirectory paths would escape base directory
    """
    weekly_dir = os.path.join(base, "weekly")
    monthly_dir = os.path.join(base, "monthly")
    logs_dir = os.path.join(base, "logs")

    # Security: Validate that subdirectories stay within base
    # This prevents path traversal if base contains malicious path components
    validate_safe_path(base, weekly_dir)
    validate_safe_path(base, monthly_dir)
    validate_safe_path(base, logs_dir)

    os.makedirs(weekly_dir, exist_ok=True)
    os.makedirs(monthly_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)


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

    Raises:
        ValueError: If the sidecar path would escape the PDF's directory
    """
    # Security: Check for path traversal components in pdf_path before processing
    # This detects paths like "invoices/../malicious.pdf"
    if '..' in pdf_path:
        raise ValueError(
            f"Path traversal detected: pdf_path '{pdf_path}' contains "
            f"parent directory references (..)"
        )

    # Replace .pdf extension with .json
    json_path = os.path.splitext(pdf_path)[0] + '.json'

    # Security: Validate that json_path stays within the same directory as pdf_path
    # This prevents path traversal attacks where a malicious pdf_path could cause
    # the sidecar to be written to an arbitrary location
    pdf_dir = os.path.dirname(os.path.abspath(pdf_path))
    validate_safe_path(pdf_dir, json_path)

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
    json_path = os.path.splitext(pdf_path)[0] + '.json'

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None
