"""
Tests for GET /api/scan endpoint.

Tests verify that the endpoint correctly checks for weekly invoice PDF existence,
handles path expansion, validates inputs, and prevents path traversal attacks.
"""

import os
import tempfile
import pytest
from pathlib import Path

# Import Flask app
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_invoice_folder():
    """
    Create a temporary folder structure for testing.

    Creates:
        {temp}/weekly/INV-20260324.pdf (exists)
        {temp}/weekly/ (empty otherwise)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create weekly subdirectory
        weekly_dir = os.path.join(tmpdir, 'weekly')
        os.makedirs(weekly_dir)

        # Create a test PDF file
        test_pdf = os.path.join(weekly_dir, 'INV-20260324.pdf')
        Path(test_pdf).touch()

        yield tmpdir


class TestScanEndpoint:
    """Tests for GET /api/scan endpoint."""

    def test_scan_pdf_exists(self, client, temp_invoice_folder):
        """Test that endpoint returns found:true when PDF exists."""
        response = client.get(
            '/api/scan',
            query_string={
                'folder': temp_invoice_folder,
                'invNum': 'INV-20260324'
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data == {"found": True}

    def test_scan_pdf_not_exists(self, client, temp_invoice_folder):
        """Test that endpoint returns found:false when PDF doesn't exist."""
        response = client.get(
            '/api/scan',
            query_string={
                'folder': temp_invoice_folder,
                'invNum': 'INV-20260331'
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data == {"found": False}

    def test_scan_missing_folder_param(self, client):
        """Test that endpoint returns 400 when folder param is missing."""
        response = client.get(
            '/api/scan',
            query_string={'invNum': 'INV-20260324'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'folder' in data['message']

    def test_scan_missing_invnum_param(self, client):
        """Test that endpoint returns 400 when invNum param is missing."""
        response = client.get(
            '/api/scan',
            query_string={'folder': '/tmp/test'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'invNum' in data['message']

    def test_scan_invalid_invnum_format(self, client, temp_invoice_folder):
        """Test that endpoint returns 400 for invalid invNum format."""
        invalid_formats = [
            'INV-2026',           # Too short
            'INV-202603241',      # Too long
            'INV-20260ABC',       # Non-numeric
            '../INV-20260324',    # Path traversal attempt
            'INV-20260324.pdf',   # Includes extension
            'invoice-20260324',   # Wrong prefix
            'INV20260324',        # Missing hyphen
        ]

        for invalid_inv in invalid_formats:
            response = client.get(
                '/api/scan',
                query_string={
                    'folder': temp_invoice_folder,
                    'invNum': invalid_inv
                }
            )

            assert response.status_code == 400, f"Failed for invNum: {invalid_inv}"
            data = response.get_json()
            assert 'error' in data
            assert 'invNum' in data['message']

    def test_scan_tilde_expansion(self, client):
        """Test that tilde (~) in folder path is properly expanded."""
        # Create a test PDF in user's temp directory
        import tempfile
        with tempfile.TemporaryDirectory(dir=os.path.expanduser('~')) as tmpdir:
            weekly_dir = os.path.join(tmpdir, 'weekly')
            os.makedirs(weekly_dir)

            test_pdf = os.path.join(weekly_dir, 'INV-20260324.pdf')
            Path(test_pdf).touch()

            # Use tilde path relative to home
            home = os.path.expanduser('~')
            relative_path = tmpdir.replace(home, '~')

            response = client.get(
                '/api/scan',
                query_string={
                    'folder': relative_path,
                    'invNum': 'INV-20260324'
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data == {"found": True}

    def test_scan_path_traversal_protection(self, client, temp_invoice_folder):
        """Test that path traversal attempts are blocked."""
        # Create a PDF outside the expected folder structure
        with tempfile.TemporaryDirectory() as other_dir:
            other_pdf = os.path.join(other_dir, 'INV-20260324.pdf')
            Path(other_pdf).touch()

            # Try to access it via path traversal
            # Note: The invNum validation should catch this, but we test defense in depth
            response = client.get(
                '/api/scan',
                query_string={
                    'folder': temp_invoice_folder,
                    'invNum': f'../../{os.path.basename(other_dir)}/INV-20260324'
                }
            )

            # Should be rejected due to invalid invNum format
            assert response.status_code == 400

    def test_scan_nonexistent_base_folder(self, client):
        """Test that endpoint handles nonexistent base folder gracefully."""
        response = client.get(
            '/api/scan',
            query_string={
                'folder': '/this/path/does/not/exist/nowhere',
                'invNum': 'INV-20260324'
            }
        )

        # Should return found:false rather than error
        assert response.status_code == 200
        data = response.get_json()
        assert data == {"found": False}

    def test_scan_valid_invnum_formats(self, client, temp_invoice_folder):
        """Test that all valid YYYYMMDD dates are accepted."""
        valid_dates = [
            'INV-20260101',  # January 1st
            'INV-20260630',  # June 30th
            'INV-20261231',  # December 31st
            'INV-19990101',  # Y2K
            'INV-20990101',  # Far future
        ]

        for valid_inv in valid_dates:
            response = client.get(
                '/api/scan',
                query_string={
                    'folder': temp_invoice_folder,
                    'invNum': valid_inv
                }
            )

            # Should not return 400 (format validation error)
            assert response.status_code in [200, 500], \
                f"Unexpected status for valid invNum: {valid_inv}"

            # If 200, should have 'found' key
            if response.status_code == 200:
                data = response.get_json()
                assert 'found' in data
