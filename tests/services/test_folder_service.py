"""
Tests for folder_service.py path validation and file operations.

Tests verify path traversal protection, path generation, and sidecar operations.
"""

import os
import tempfile
import json
import pytest
from pathlib import Path

# Import service functions
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.folder_service import (
    validate_safe_path,
    weekly_path,
    monthly_path,
    ensure_folders,
    write_sidecar,
    read_sidecar,
    expand_path
)


class TestValidateSafePath:
    """Tests for validate_safe_path function."""

    def test_valid_path_within_base(self):
        """Test that valid paths within base directory pass validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir
            valid_target = os.path.join(tmpdir, "weekly", "INV-20260324.pdf")

            # Should not raise
            validate_safe_path(base, valid_target)

    def test_valid_path_same_as_base(self):
        """Test that base directory itself is considered valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise
            validate_safe_path(tmpdir, tmpdir)

    def test_path_traversal_parent_directory(self):
        """Test that path traversal using .. is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "invoices")
            os.makedirs(base)

            # Try to escape to parent using ../
            malicious_target = os.path.join(base, "..", "etc", "passwd")

            with pytest.raises(ValueError, match="Path traversal detected"):
                validate_safe_path(base, malicious_target)

    def test_path_traversal_absolute_path(self):
        """Test that absolute paths outside base are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir

            # Try to access /etc/passwd
            with pytest.raises(ValueError, match="Path traversal detected"):
                validate_safe_path(base, "/etc/passwd")

    def test_path_traversal_sibling_directory(self):
        """Test that escaping to sibling directory is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two sibling directories
            invoices_dir = os.path.join(tmpdir, "invoices")
            secrets_dir = os.path.join(tmpdir, "secrets")
            os.makedirs(invoices_dir)
            os.makedirs(secrets_dir)

            # Try to access sibling directory
            malicious_target = os.path.join(invoices_dir, "..", "secrets", "key.txt")

            with pytest.raises(ValueError, match="Path traversal detected"):
                validate_safe_path(invoices_dir, malicious_target)

    def test_path_with_symbolic_link(self):
        """Test that symbolic links are resolved and validated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "invoices")
            outside = os.path.join(tmpdir, "outside")
            os.makedirs(base)
            os.makedirs(outside)

            # Create a symbolic link from base to outside
            link_path = os.path.join(base, "link_to_outside")
            try:
                os.symlink(outside, link_path)

                # Try to access path through symlink (should be blocked)
                target = os.path.join(link_path, "file.txt")

                with pytest.raises(ValueError, match="Path traversal detected"):
                    validate_safe_path(base, target)
            except OSError:
                # Skip if symlinks not supported (e.g., Windows without admin)
                pytest.skip("Symbolic links not supported on this system")

    def test_nested_valid_path(self):
        """Test that deeply nested paths within base are valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir
            nested_target = os.path.join(tmpdir, "a", "b", "c", "d", "file.pdf")

            # Should not raise
            validate_safe_path(base, nested_target)


class TestWeeklyPath:
    """Tests for weekly_path function."""

    def test_weekly_path_normal(self):
        """Test normal weekly path generation."""
        base = "/home/user/invoices"
        inv_num = "INV-20260324"

        result = weekly_path(base, inv_num)

        assert result == "/home/user/invoices/weekly/INV-20260324.pdf"

    def test_weekly_path_with_traversal_attempt(self):
        """Test that path traversal attempts in inv_num are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir
            malicious_inv = "../../etc/passwd"

            with pytest.raises(ValueError, match="Path traversal detected"):
                weekly_path(base, malicious_inv)

    def test_weekly_path_with_absolute_inv_num(self):
        """Test that absolute paths in inv_num are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir
            malicious_inv = "/etc/passwd"

            with pytest.raises(ValueError, match="Path traversal detected"):
                weekly_path(base, malicious_inv)


class TestMonthlyPath:
    """Tests for monthly_path function."""

    def test_monthly_path_normal(self):
        """Test normal monthly path generation."""
        base = "/home/user/invoices"
        year = 2026
        month = 3

        result = monthly_path(base, year, month)

        assert result == "/home/user/invoices/monthly/RPT-2026-03.pdf"

    def test_monthly_path_single_digit_month(self):
        """Test that single-digit months are zero-padded."""
        base = "/home/user/invoices"
        year = 2026
        month = 1

        result = monthly_path(base, year, month)

        assert result == "/home/user/invoices/monthly/RPT-2026-01.pdf"

    def test_monthly_path_december(self):
        """Test monthly path for December."""
        base = "/home/user/invoices"
        year = 2026
        month = 12

        result = monthly_path(base, year, month)

        assert result == "/home/user/invoices/monthly/RPT-2026-12.pdf"


class TestEnsureFolders:
    """Tests for ensure_folders function."""

    def test_ensure_folders_creates_subdirectories(self):
        """Test that weekly/ and monthly/ subdirectories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir

            ensure_folders(base)

            weekly_dir = os.path.join(base, "weekly")
            monthly_dir = os.path.join(base, "monthly")

            assert os.path.exists(weekly_dir)
            assert os.path.isdir(weekly_dir)
            assert os.path.exists(monthly_dir)
            assert os.path.isdir(monthly_dir)

    def test_ensure_folders_idempotent(self):
        """Test that calling ensure_folders multiple times is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir

            # Call twice
            ensure_folders(base)
            ensure_folders(base)

            # Should still exist
            assert os.path.exists(os.path.join(base, "weekly"))
            assert os.path.exists(os.path.join(base, "monthly"))

    def test_ensure_folders_with_existing_files(self):
        """Test that ensure_folders works when subdirectories already exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = tmpdir

            # Pre-create weekly/ with a file
            weekly_dir = os.path.join(base, "weekly")
            os.makedirs(weekly_dir)
            test_file = os.path.join(weekly_dir, "test.pdf")
            Path(test_file).touch()

            # Should not fail
            ensure_folders(base)

            # File should still exist
            assert os.path.exists(test_file)


class TestWriteSidecar:
    """Tests for write_sidecar function."""

    def test_write_sidecar_normal(self):
        """Test normal sidecar file creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "INV-20260324.pdf")
            data = {"totalHours": 40, "dailyHours": {"Monday": 8}}

            write_sidecar(pdf_path, data)

            json_path = os.path.join(tmpdir, "INV-20260324.json")
            assert os.path.exists(json_path)

            # Verify contents
            with open(json_path, 'r') as f:
                saved_data = json.load(f)
            assert saved_data == data

    def test_write_sidecar_overwrites_existing(self):
        """Test that write_sidecar overwrites existing sidecar files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "INV-20260324.pdf")
            json_path = os.path.join(tmpdir, "INV-20260324.json")

            # Write initial data
            initial_data = {"totalHours": 35}
            write_sidecar(pdf_path, initial_data)

            # Overwrite with new data
            new_data = {"totalHours": 40}
            write_sidecar(pdf_path, new_data)

            # Verify new data
            with open(json_path, 'r') as f:
                saved_data = json.load(f)
            assert saved_data == new_data

    def test_write_sidecar_with_unicode(self):
        """Test that sidecar handles Unicode characters correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "INV-20260324.pdf")
            data = {"name": "François", "note": "Café ☕"}

            write_sidecar(pdf_path, data)

            json_path = os.path.join(tmpdir, "INV-20260324.json")
            with open(json_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            assert saved_data == data

    def test_write_sidecar_path_traversal_protection(self):
        """Test that write_sidecar prevents path traversal attacks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory
            invoices_dir = os.path.join(tmpdir, "invoices")
            os.makedirs(invoices_dir)

            # Try to write sidecar for a PDF path that escapes the directory
            malicious_pdf = os.path.join(invoices_dir, "..", "malicious.pdf")
            data = {"attack": "attempted"}

            # Should raise ValueError due to path traversal
            with pytest.raises(ValueError, match="Path traversal detected"):
                write_sidecar(malicious_pdf, data)


class TestReadSidecar:
    """Tests for read_sidecar function."""

    def test_read_sidecar_existing(self):
        """Test reading an existing sidecar file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "INV-20260324.pdf")
            json_path = os.path.join(tmpdir, "INV-20260324.json")

            # Create sidecar
            data = {"totalHours": 40, "dailyHours": {"Monday": 8}}
            with open(json_path, 'w') as f:
                json.dump(data, f)

            # Read it back
            result = read_sidecar(pdf_path)
            assert result == data

    def test_read_sidecar_nonexistent(self):
        """Test reading a non-existent sidecar file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "INV-20260324.pdf")

            result = read_sidecar(pdf_path)
            assert result is None

    def test_read_sidecar_malformed_json(self):
        """Test that malformed JSON returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "INV-20260324.pdf")
            json_path = os.path.join(tmpdir, "INV-20260324.json")

            # Create malformed JSON
            with open(json_path, 'w') as f:
                f.write("{ invalid json }")

            result = read_sidecar(pdf_path)
            assert result is None


class TestExpandPath:
    """Tests for expand_path function."""

    def test_expand_path_with_tilde(self):
        """Test that tilde is expanded to home directory."""
        path = "~/Documents/invoices"
        result = expand_path(path)

        # Should expand to actual home directory
        assert result.startswith(os.path.expanduser('~'))
        assert "Documents/invoices" in result

    def test_expand_path_without_tilde(self):
        """Test that paths without tilde are unchanged."""
        path = "/home/user/invoices"
        result = expand_path(path)

        assert result == path

    def test_expand_path_relative(self):
        """Test that relative paths are handled."""
        path = "invoices/weekly"
        result = expand_path(path)

        # Should return the path as-is (expanduser doesn't change relative paths)
        assert result == path
