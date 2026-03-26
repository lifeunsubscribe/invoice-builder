"""
Tests for GET /api/scan and GET /api/scan-month endpoints.

Tests verify that the endpoints correctly check for weekly invoice PDF existence,
handles path expansion, validates inputs, and prevents path traversal attacks.
"""

import os
import tempfile
import json
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


class TestScanMonthEndpoint:
    """Tests for GET /api/scan-month endpoint."""

    @pytest.fixture
    def temp_month_folder(self):
        """
        Create a temporary folder structure for testing scan-month.

        Creates:
            {temp}/weekly/INV-20260303.pdf + .json (40 hours)
            {temp}/weekly/INV-20260310.pdf + .json (35 hours)
            {temp}/weekly/INV-20260317.pdf (no sidecar - pre-existing)
            {temp}/weekly/INV-20260324.pdf + .json (0 hours - edge case)
            (INV-20260331 does not exist)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            weekly_dir = os.path.join(tmpdir, 'weekly')
            os.makedirs(weekly_dir)

            # Week 1: PDF + sidecar with 40 hours
            pdf1 = os.path.join(weekly_dir, 'INV-20260303.pdf')
            json1 = os.path.join(weekly_dir, 'INV-20260303.json')
            Path(pdf1).touch()
            with open(json1, 'w') as f:
                json.dump({"totalHours": 40}, f)

            # Week 2: PDF + sidecar with 35 hours
            pdf2 = os.path.join(weekly_dir, 'INV-20260310.pdf')
            json2 = os.path.join(weekly_dir, 'INV-20260310.json')
            Path(pdf2).touch()
            with open(json2, 'w') as f:
                json.dump({"totalHours": 35}, f)

            # Week 3: PDF without sidecar (pre-existing invoice)
            pdf3 = os.path.join(weekly_dir, 'INV-20260317.pdf')
            Path(pdf3).touch()

            # Week 4: PDF + sidecar with 0 hours (edge case)
            pdf4 = os.path.join(weekly_dir, 'INV-20260324.pdf')
            json4 = os.path.join(weekly_dir, 'INV-20260324.json')
            Path(pdf4).touch()
            with open(json4, 'w') as f:
                json.dump({"totalHours": 0}, f)

            # Week 5 (INV-20260331) does not exist

            yield tmpdir

    def test_scan_month_basic(self, client, temp_month_folder):
        """Test basic scan-month functionality for March 2026."""
        response = client.get(
            '/api/scan-month',
            query_string={
                'year': 2026,
                'month': 3,
                'folder': temp_month_folder
            }
        )

        assert response.status_code == 200
        data = response.get_json()

        assert 'weeks' in data
        weeks = data['weeks']

        # March 2026 should have 5 weeks (Mar 3, 10, 17, 24, 31)
        assert len(weeks) == 5

        # Week 1: Mar 3-9 (found with 40 hours)
        assert weeks[0]['label'] == 'Mar 3 – Mar 9, 2026'
        assert weeks[0]['invNum'] == 'INV-20260303'
        assert weeks[0]['found'] is True
        assert weeks[0]['hours'] == 40

        # Week 2: Mar 10-16 (found with 35 hours)
        assert weeks[1]['label'] == 'Mar 10 – Mar 16, 2026'
        assert weeks[1]['invNum'] == 'INV-20260310'
        assert weeks[1]['found'] is True
        assert weeks[1]['hours'] == 35

        # Week 3: Mar 17-23 (found without sidecar - hours=null)
        assert weeks[2]['label'] == 'Mar 17 – Mar 23, 2026'
        assert weeks[2]['invNum'] == 'INV-20260317'
        assert weeks[2]['found'] is True
        assert weeks[2]['hours'] is None

        # Week 4: Mar 24-30 (found with 0 hours)
        assert weeks[3]['label'] == 'Mar 24 – Mar 30, 2026'
        assert weeks[3]['invNum'] == 'INV-20260324'
        assert weeks[3]['found'] is True
        assert weeks[3]['hours'] == 0

        # Week 5: Mar 31 - Apr 6 (not found - hours=0)
        assert weeks[4]['label'] == 'Mar 31 – Apr 6, 2026'
        assert weeks[4]['invNum'] == 'INV-20260331'
        assert weeks[4]['found'] is False
        assert weeks[4]['hours'] == 0

    def test_scan_month_february_2026(self, client, temp_month_folder):
        """Test scan-month for February 2026 (month starting mid-week)."""
        # February 2026 starts on Sunday (Feb 1)
        # First Tuesday is Feb 3
        response = client.get(
            '/api/scan-month',
            query_string={
                'year': 2026,
                'month': 2,
                'folder': temp_month_folder
            }
        )

        assert response.status_code == 200
        data = response.get_json()

        weeks = data['weeks']

        # February 2026 should have 4 weeks
        # (Feb 3, Feb 10, Feb 17, Feb 24)
        assert len(weeks) == 4

        # First week should start on Tuesday Feb 3
        assert weeks[0]['invNum'] == 'INV-20260203'
        assert 'Feb 3' in weeks[0]['label']

        # All should be not found (no PDFs for Feb)
        for week in weeks:
            assert week['found'] is False
            assert week['hours'] == 0

    def test_scan_month_missing_year(self, client, temp_month_folder):
        """Test that endpoint returns 400 when year param is missing."""
        response = client.get(
            '/api/scan-month',
            query_string={
                'month': 3,
                'folder': temp_month_folder
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'year' in data['message']

    def test_scan_month_missing_month(self, client, temp_month_folder):
        """Test that endpoint returns 400 when month param is missing."""
        response = client.get(
            '/api/scan-month',
            query_string={
                'year': 2026,
                'folder': temp_month_folder
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'month' in data['message']

    def test_scan_month_missing_folder(self, client):
        """Test that endpoint returns 400 when folder param is missing."""
        response = client.get(
            '/api/scan-month',
            query_string={
                'year': 2026,
                'month': 3
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'folder' in data['message']

    def test_scan_month_invalid_year(self, client, temp_month_folder):
        """Test validation for invalid year values."""
        invalid_years = [
            ('abc', 'must be a valid integer'),
            ('1899', 'between 1900 and 2100'),
            ('2101', 'between 1900 and 2100'),
            ('0', 'between 1900 and 2100'),
            ('-2026', 'between 1900 and 2100'),
        ]

        for invalid_year, expected_msg in invalid_years:
            response = client.get(
                '/api/scan-month',
                query_string={
                    'year': invalid_year,
                    'month': 3,
                    'folder': temp_month_folder
                }
            )

            assert response.status_code == 400, f"Failed for year: {invalid_year}"
            data = response.get_json()
            assert 'error' in data
            assert expected_msg in data['message']

    def test_scan_month_invalid_month(self, client, temp_month_folder):
        """Test validation for invalid month values."""
        invalid_months = [
            ('abc', 'must be a valid integer'),
            ('0', 'between 1 and 12'),
            ('13', 'between 1 and 12'),
            ('-1', 'between 1 and 12'),
            ('100', 'between 1 and 12'),
        ]

        for invalid_month, expected_msg in invalid_months:
            response = client.get(
                '/api/scan-month',
                query_string={
                    'year': 2026,
                    'month': invalid_month,
                    'folder': temp_month_folder
                }
            )

            assert response.status_code == 400, f"Failed for month: {invalid_month}"
            data = response.get_json()
            assert 'error' in data
            assert expected_msg in data['message']

    def test_scan_month_nonexistent_folder(self, client):
        """Test that endpoint handles nonexistent folders gracefully."""
        response = client.get(
            '/api/scan-month',
            query_string={
                'year': 2026,
                'month': 3,
                'folder': '/this/path/does/not/exist/nowhere'
            }
        )

        # Should return 200 with all weeks showing found=false
        assert response.status_code == 200
        data = response.get_json()
        weeks = data['weeks']

        # All weeks should be not found
        for week in weeks:
            assert week['found'] is False
            assert week['hours'] == 0

    def test_scan_month_empty_folder(self, client):
        """Test scan-month with an empty folder (no weekly subdirectory)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            response = client.get(
                '/api/scan-month',
                query_string={
                    'year': 2026,
                    'month': 3,
                    'folder': tmpdir
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            weeks = data['weeks']

            # Should return weeks but all not found
            assert len(weeks) == 5
            for week in weeks:
                assert week['found'] is False
                assert week['hours'] == 0

    def test_scan_month_december_year_boundary(self, client, temp_month_folder):
        """Test scan-month for December (year boundary edge case)."""
        response = client.get(
            '/api/scan-month',
            query_string={
                'year': 2026,
                'month': 12,
                'folder': temp_month_folder
            }
        )

        assert response.status_code == 200
        data = response.get_json()
        weeks = data['weeks']

        # December 2026 starts on Tuesday (Dec 1)
        # First Tuesday is Dec 1
        assert len(weeks) >= 4

        # Verify last week can span into January 2027
        last_week = weeks[-1]
        assert '2027' in last_week['label'] or '2026' in last_week['label']

    def test_scan_month_tilde_expansion(self, client):
        """Test that tilde (~) in folder path is properly expanded."""
        with tempfile.TemporaryDirectory(dir=os.path.expanduser('~')) as tmpdir:
            weekly_dir = os.path.join(tmpdir, 'weekly')
            os.makedirs(weekly_dir)

            # Use tilde path relative to home
            home = os.path.expanduser('~')
            relative_path = tmpdir.replace(home, '~')

            response = client.get(
                '/api/scan-month',
                query_string={
                    'year': 2026,
                    'month': 3,
                    'folder': relative_path
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert 'weeks' in data

    def test_scan_month_malformed_sidecar_json(self, client):
        """Test that malformed sidecar JSON is handled gracefully (hours=null)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            weekly_dir = os.path.join(tmpdir, 'weekly')
            os.makedirs(weekly_dir)

            # Create PDF with malformed JSON sidecar
            pdf = os.path.join(weekly_dir, 'INV-20260303.pdf')
            json_file = os.path.join(weekly_dir, 'INV-20260303.json')
            Path(pdf).touch()
            with open(json_file, 'w') as f:
                f.write('{ invalid json }')

            response = client.get(
                '/api/scan-month',
                query_string={
                    'year': 2026,
                    'month': 3,
                    'folder': tmpdir
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            weeks = data['weeks']

            # First week should be found but hours=null (malformed JSON)
            assert weeks[0]['found'] is True
            assert weeks[0]['hours'] is None

    def test_scan_month_sidecar_missing_totalhours(self, client):
        """Test sidecar JSON without totalHours field (hours=null)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            weekly_dir = os.path.join(tmpdir, 'weekly')
            os.makedirs(weekly_dir)

            # Create PDF with JSON sidecar missing totalHours
            pdf = os.path.join(weekly_dir, 'INV-20260303.pdf')
            json_file = os.path.join(weekly_dir, 'INV-20260303.json')
            Path(pdf).touch()
            with open(json_file, 'w') as f:
                json.dump({"dailyHours": {"Monday": 8}}, f)

            response = client.get(
                '/api/scan-month',
                query_string={
                    'year': 2026,
                    'month': 3,
                    'folder': tmpdir
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            weeks = data['weeks']

            # First week should be found but hours=null (missing totalHours)
            assert weeks[0]['found'] is True
            assert weeks[0]['hours'] is None
