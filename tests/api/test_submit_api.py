"""
Tests for POST /api/submit/weekly and POST /api/submit/monthly endpoints.

Tests verify PDF generation, sidecar JSON creation, email sending,
overwrite detection, and error handling.
"""

import os
import tempfile
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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
def temp_config():
    """Create a temporary config.json file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_data = {
            "name": "Test User",
            "address": "123 Test St",
            "personalEmail": "test@example.com",
            "rate": 25.00,
            "clientName": "Test Client",
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "accent": "#c47a86",
            "invoiceNote": "Thank you!",
            "saveFolder": tmpdir
        }

        config_path = os.path.join(tmpdir, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)

        yield tmpdir, config_path, config_data


class TestSubmitWeeklyEndpoint:
    """Tests for POST /api/submit/weekly endpoint."""

    def test_submit_weekly_success(self, client, temp_config):
        """Test successful weekly invoice submission with all steps."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "hours": {
                "Monday": 8,
                "Tuesday": 8,
                "Wednesday": 8,
                "Thursday": 8,
                "Friday": 8,
                "Saturday": 0,
                "Sunday": 0
            },
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324",
                "dayDates": {
                    "Monday": "Mar 24",
                    "Tuesday": "Mar 25",
                    "Wednesday": "Mar 26",
                    "Thursday": "Mar 27",
                    "Friday": "Mar 28",
                    "Saturday": "Mar 29",
                    "Sunday": "Mar 30"
                }
            },
            "template": "morning-light"
        }

        # Mock services
        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    # Setup mocks
                    mock_pdf.return_value = b'%PDF-1.4 fake pdf content'
                    mock_email.return_value = {"success": True}

                    # Make request
                    response = client.post(
                        '/api/submit/weekly',
                        json=payload,
                        content_type='application/json'
                    )

                    # Verify response
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    assert 'saved' in data
                    assert data['sent'] == ["client@example.com", "accountant@example.com"]
                    assert data['overwrite'] is False  # First save

                    # Verify PDF was saved
                    pdf_path = os.path.join(tmpdir, 'weekly', 'INV-20260324.pdf')
                    assert os.path.exists(pdf_path)

                    # Verify sidecar JSON was created
                    json_path = os.path.join(tmpdir, 'weekly', 'INV-20260324.json')
                    assert os.path.exists(json_path)

                    with open(json_path, 'r', encoding='utf-8') as f:
                        sidecar_data = json.load(f)
                        assert sidecar_data['totalHours'] == 40
                        assert sidecar_data['dailyHours'] == payload['hours']

                    # Verify render_weekly_pdf was called correctly
                    mock_pdf.assert_called_once()
                    call_args = mock_pdf.call_args[1]
                    assert call_args['template_id'] == 'morning-light'
                    assert call_args['hours'] == payload['hours']

                    # Verify email was sent
                    mock_email.assert_called_once()

    def test_submit_weekly_overwrite_detection(self, client, temp_config):
        """Test that overwrite flag is set when PDF already exists."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "hours": {"Monday": 8, "Tuesday": 8, "Wednesday": 8, "Thursday": 8,
                      "Friday": 8, "Saturday": 0, "Sunday": 0},
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324",
                "dayDates": {}
            },
            "template": "morning-light"
        }

        # Create existing PDF
        weekly_dir = os.path.join(tmpdir, 'weekly')
        os.makedirs(weekly_dir, exist_ok=True)
        existing_pdf = os.path.join(weekly_dir, 'INV-20260324.pdf')
        Path(existing_pdf).write_bytes(b'existing content')

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 new content'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/weekly',
                        json=payload,
                        content_type='application/json'
                    )

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['overwrite'] is True  # PDF existed before

    def test_submit_weekly_email_failure_partial_success(self, client, temp_config):
        """Test that PDF is saved even when email fails (partial success)."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "hours": {"Monday": 8, "Tuesday": 8, "Wednesday": 8, "Thursday": 8,
                      "Friday": 8, "Saturday": 0, "Sunday": 0},
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324",
                "dayDates": {}
            },
            "template": "morning-light"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 fake pdf'
                    mock_email.return_value = {
                        "success": False,
                        "error": "SMTP connection failed"
                    }

                    response = client.post(
                        '/api/submit/weekly',
                        json=payload,
                        content_type='application/json'
                    )

                    # Should still return 200 (partial success)
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True  # PDF was saved
                    assert data['sent'] == []  # No emails sent
                    assert 'emailError' in data
                    assert data['emailError'] == 'SMTP connection failed'

                    # Verify PDF was still saved
                    pdf_path = os.path.join(tmpdir, 'weekly', 'INV-20260324.pdf')
                    assert os.path.exists(pdf_path)

    def test_submit_weekly_missing_required_fields(self, client):
        """Test validation for missing required fields."""
        incomplete_payloads = [
            {},  # All missing
            {"hours": {}},  # Missing other fields
            {"hours": {}, "clientEmail": "test@test.com"},  # Still missing fields
        ]

        for payload in incomplete_payloads:
            response = client.post(
                '/api/submit/weekly',
                json=payload,
                content_type='application/json'
            )

            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'error' in data

    def test_submit_weekly_invalid_json(self, client):
        """Test that invalid JSON returns 400."""
        response = client.post(
            '/api/submit/weekly',
            data='not valid json',
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'JSON' in data['error']

    def test_submit_weekly_invalid_template(self, client, temp_config):
        """Test that invalid template ID is rejected."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "hours": {"Monday": 8, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
                      "Friday": 0, "Saturday": 0, "Sunday": 0},
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324",
                "dayDates": {}
            },
            "template": "invalid-template-name"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            response = client.post(
                '/api/submit/weekly',
                json=payload,
                content_type='application/json'
            )

            # PDF service should raise ValueError for invalid template
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False

    def test_submit_weekly_missing_config(self, client):
        """Test that missing config.json returns 500."""
        payload = {
            "hours": {"Monday": 8, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
                      "Friday": 0, "Saturday": 0, "Sunday": 0},
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324",
                "dayDates": {}
            },
            "template": "morning-light"
        }

        with patch('app.api.submit_api.get_config_path', return_value='/nonexistent/config.json'):
            response = client.post(
                '/api/submit/weekly',
                json=payload,
                content_type='application/json'
            )

            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'Configuration not found' in data['error']


class TestSubmitMonthlyEndpoint:
    """Tests for POST /api/submit/monthly endpoint."""

    def test_submit_monthly_success(self, client, temp_config):
        """Test successful monthly report submission."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "weekData": [
                {"label": "Mar 3 – Mar 9", "hours": 40},
                {"label": "Mar 10 – Mar 16", "hours": 40},
                {"label": "Mar 17 – Mar 23", "hours": 40},
                {"label": "Mar 24 – Mar 30", "hours": 40}
            ],
            "year": 2026,
            "month": 3,
            "accountantEmail": "accountant@example.com"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_monthly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 fake monthly pdf'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/monthly',
                        json=payload,
                        content_type='application/json'
                    )

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    assert 'saved' in data
                    assert data['sent'] == ["accountant@example.com"]
                    assert data['overwrite'] is False  # First save

                    # Verify PDF was saved
                    pdf_path = os.path.join(tmpdir, 'monthly', 'RPT-2026-03.pdf')
                    assert os.path.exists(pdf_path)

                    # Verify render_monthly_pdf was called with correct month label
                    mock_pdf.assert_called_once()
                    call_args = mock_pdf.call_args[1]
                    assert call_args['month_label'] == 'March 2026'
                    assert call_args['week_data'] == payload['weekData']

    def test_submit_monthly_overwrite_detection(self, client, temp_config):
        """Test that overwrite flag is set when monthly PDF already exists."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "weekData": [{"label": "Mar 3 – Mar 9", "hours": 40}],
            "year": 2026,
            "month": 3,
            "accountantEmail": "accountant@example.com"
        }

        # Create existing monthly PDF
        monthly_dir = os.path.join(tmpdir, 'monthly')
        os.makedirs(monthly_dir, exist_ok=True)
        existing_pdf = os.path.join(monthly_dir, 'RPT-2026-03.pdf')
        Path(existing_pdf).write_bytes(b'existing monthly content')

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_monthly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 new monthly content'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/monthly',
                        json=payload,
                        content_type='application/json'
                    )

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['overwrite'] is True  # PDF existed before

    def test_submit_monthly_missing_required_fields(self, client):
        """Test validation for missing required fields."""
        response = client.post(
            '/api/submit/monthly',
            json={"year": 2026},  # Missing month, weekData, accountantEmail
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Missing required fields' in data['error']

    def test_submit_monthly_email_failure(self, client, temp_config):
        """Test monthly submission handles email failure gracefully."""
        tmpdir, config_path, config_data = temp_config

        payload = {
            "weekData": [{"label": "Mar 3 – Mar 9", "hours": 40}],
            "year": 2026,
            "month": 3,
            "accountantEmail": "accountant@example.com"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_monthly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 fake monthly pdf'
                    mock_email.return_value = {
                        "success": False,
                        "error": "Authentication failed"
                    }

                    response = client.post(
                        '/api/submit/monthly',
                        json=payload,
                        content_type='application/json'
                    )

                    # Partial success
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    assert data['sent'] == []
                    assert 'emailError' in data
                    assert data['overwrite'] is False  # First save


class TestEmailValidation:
    """Tests for email validation in submit endpoints."""

    def test_submit_weekly_invalid_client_email(self, client):
        """Test that invalid client email is rejected."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "no@domain@double.com",
            "spaces in@email.com",
            "",
            "nodomain@",
            "user@",
            123,  # Not a string
            None,
            {"email": "test@test.com"}  # Object instead of string
        ]

        for invalid_email in invalid_emails:
            payload = {
                "hours": {"Monday": 8, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
                          "Friday": 0, "Saturday": 0, "Sunday": 0},
                "clientEmail": invalid_email,
                "accountantEmail": "valid@example.com",
                "week": {
                    "start": "March 24",
                    "end": "March 30, 2026",
                    "invNum": "INV-20260324",
                    "dayDates": {}
                },
                "template": "morning-light"
            }

            response = client.post(
                '/api/submit/weekly',
                json=payload,
                content_type='application/json'
            )

            assert response.status_code == 400, f"Expected 400 for invalid client email: {invalid_email}"
            data = response.get_json()
            assert data['success'] is False
            assert 'email' in data['error'].lower() or 'email' in data['message'].lower()

    def test_submit_weekly_invalid_accountant_email(self, client):
        """Test that invalid accountant email is rejected."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "no@domain@double.com",
            ""
        ]

        for invalid_email in invalid_emails:
            payload = {
                "hours": {"Monday": 8, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
                          "Friday": 0, "Saturday": 0, "Sunday": 0},
                "clientEmail": "valid@example.com",
                "accountantEmail": invalid_email,
                "week": {
                    "start": "March 24",
                    "end": "March 30, 2026",
                    "invNum": "INV-20260324",
                    "dayDates": {}
                },
                "template": "morning-light"
            }

            response = client.post(
                '/api/submit/weekly',
                json=payload,
                content_type='application/json'
            )

            assert response.status_code == 400, f"Expected 400 for invalid accountant email: {invalid_email}"
            data = response.get_json()
            assert data['success'] is False
            assert 'email' in data['error'].lower() or 'email' in data['message'].lower()

    def test_submit_weekly_valid_email_formats(self, client, temp_config):
        """Test that various valid email formats are accepted."""
        tmpdir, config_path, config_data = temp_config

        valid_emails = [
            "user@example.com",
            "test.user@example.com",
            "test+tag@example.co.uk",
            "user123@test-domain.com",
            "UPPERCASE@EXAMPLE.COM",
            "first.last@subdomain.example.com"
        ]

        for valid_email in valid_emails:
            payload = {
                "hours": {"Monday": 8, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
                          "Friday": 0, "Saturday": 0, "Sunday": 0},
                "clientEmail": valid_email,
                "accountantEmail": "accountant@example.com",
                "week": {
                    "start": "March 24",
                    "end": "March 30, 2026",
                    "invNum": f"INV-{valid_email.replace('@', '-').replace('.', '-')}",
                    "dayDates": {}
                },
                "template": "morning-light"
            }

            with patch('app.api.submit_api.get_config_path', return_value=config_path):
                with patch('app.api.submit_api.render_weekly_pdf') as mock_pdf:
                    with patch('app.api.submit_api.send_invoice_email') as mock_email:
                        mock_pdf.return_value = b'%PDF-1.4 fake pdf'
                        mock_email.return_value = {"success": True}

                        response = client.post(
                            '/api/submit/weekly',
                            json=payload,
                            content_type='application/json'
                        )

                        assert response.status_code == 200, f"Expected 200 for valid email: {valid_email}"
                        data = response.get_json()
                        assert data['success'] is True

    def test_submit_monthly_invalid_accountant_email(self, client):
        """Test that invalid accountant email is rejected in monthly endpoint."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "",
            123
        ]

        for invalid_email in invalid_emails:
            payload = {
                "weekData": [{"label": "Mar 3 – Mar 9", "hours": 40}],
                "year": 2026,
                "month": 3,
                "accountantEmail": invalid_email
            }

            response = client.post(
                '/api/submit/monthly',
                json=payload,
                content_type='application/json'
            )

            assert response.status_code == 400, f"Expected 400 for invalid email: {invalid_email}"
            data = response.get_json()
            assert data['success'] is False
            assert 'email' in data['error'].lower() or 'email' in data['message'].lower()


class TestSubmitArraySizeValidation:
    """Tests for array size validation to prevent DoS attacks."""

    def test_submit_weekly_with_oversized_hours_dict(self, client, temp_config):
        """Test that weekly endpoint rejects oversized hours dictionary."""
        from app.middleware.request_validator import MAX_ARRAY_SIZE

        tmpdir, config_path, config_data = temp_config

        # Create hours dict exceeding MAX_ARRAY_SIZE
        oversized_hours = {f"Day_{i}": 8 for i in range(MAX_ARRAY_SIZE + 1)}

        payload = {
            "hours": oversized_hours,
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324"
            },
            "template": "morning-light"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            response = client.post(
                '/api/submit/weekly',
                json=payload,
                content_type='application/json'
            )

            # Should reject with 400
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'hours' in data['message']
            assert 'exceeds maximum allowed size' in data['message']

    def test_submit_weekly_with_valid_hours_size(self, client, temp_config):
        """Test that weekly endpoint accepts hours dict within size limit."""
        tmpdir, config_path, config_data = temp_config

        # Normal sized hours dict (7 days)
        normal_hours = {
            "Monday": 8,
            "Tuesday": 8,
            "Wednesday": 8,
            "Thursday": 8,
            "Friday": 8,
            "Saturday": 0,
            "Sunday": 0
        }

        payload = {
            "hours": normal_hours,
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324"
            },
            "template": "morning-light"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 fake pdf'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/weekly',
                        json=payload,
                        content_type='application/json'
                    )

                    # Should succeed
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True

    def test_submit_monthly_with_oversized_week_data(self, client, temp_config):
        """Test that monthly endpoint rejects oversized weekData array."""
        from app.middleware.request_validator import MAX_ARRAY_SIZE

        tmpdir, config_path, config_data = temp_config

        # Create weekData array exceeding MAX_ARRAY_SIZE
        oversized_week_data = [
            {"label": f"Week {i}", "hours": 40}
            for i in range(MAX_ARRAY_SIZE + 1)
        ]

        payload = {
            "weekData": oversized_week_data,
            "year": 2026,
            "month": 3,
            "accountantEmail": "accountant@example.com"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            response = client.post(
                '/api/submit/monthly',
                json=payload,
                content_type='application/json'
            )

            # Should reject with 400
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'weekData' in data['message']
            assert 'exceeds maximum allowed size' in data['message']

    def test_submit_monthly_with_valid_week_data_size(self, client, temp_config):
        """Test that monthly endpoint accepts weekData within size limit."""
        tmpdir, config_path, config_data = temp_config

        # Normal sized weekData (4-5 weeks per month)
        normal_week_data = [
            {"label": "Mar 3 – Mar 9, 2026", "hours": 40},
            {"label": "Mar 10 – Mar 16, 2026", "hours": 40},
            {"label": "Mar 17 – Mar 23, 2026", "hours": 40},
            {"label": "Mar 24 – Mar 30, 2026", "hours": 40}
        ]

        payload = {
            "weekData": normal_week_data,
            "year": 2026,
            "month": 3,
            "accountantEmail": "accountant@example.com"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_monthly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 fake pdf'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/monthly',
                        json=payload,
                        content_type='application/json'
                    )

                    # Should succeed
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True


@pytest.fixture
def temp_config_string_rate():
    """
    Like temp_config but with rate stored as a string.

    Reproduces the production state where the profile form saves rate as
    a string. The submit endpoints used to crash with
    "can't multiply sequence by non-int of type 'float'" in this case
    because the email-body math did `total_hours * config.get('rate', 0)`
    without coercing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_data = {
            "name": "Test User",
            "address": "123 Test St",
            "personalEmail": "test@example.com",
            "rate": "25",  # string, not numeric
            "clientName": "Test Client",
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "accent": "#c47a86",
            "invoiceNote": "Thank you!",
            "saveFolder": tmpdir,
            "clients": [
                {
                    "id": "client-1",
                    "name": "Test Patient",
                    "address": "456 Patient St",
                    "objective": "Care plan",
                    "meds": [],
                    "defaultShift": {"start": "09:00", "end": "17:00"},
                }
            ],
            "activeClientId": "client-1",
        }

        config_path = os.path.join(tmpdir, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)

        yield tmpdir, config_path, config_data


class TestRateAsStringRegression:
    """
    Regression tests for the bug where config rate is saved as a string.

    Profile form input saves rate as e.g. "25" instead of 25.0. The submit
    endpoints used `total_hours * config.get('rate', 0)` directly, which
    raises TypeError on string rate. The fix routes all config loads
    through load_config() which coerces rate to float.
    """

    def test_load_config_coerces_string_rate(self, temp_config_string_rate):
        """load_config() must coerce string rate to float."""
        _, config_path, _ = temp_config_string_rate
        from app.api import submit_api

        with patch.object(submit_api, 'get_config_path', return_value=config_path):
            cfg = submit_api.load_config()
            assert isinstance(cfg['rate'], float)
            assert cfg['rate'] == 25.0

    def test_load_config_handles_garbage_rate(self):
        """load_config() must default to 0.0 on bad rate values."""
        from app.api import submit_api

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump({"rate": "not a number", "saveFolder": tmpdir}, f)

            with patch.object(submit_api, 'get_config_path', return_value=config_path):
                cfg = submit_api.load_config()
                assert cfg['rate'] == 0.0

    def test_submit_weekly_with_string_rate(self, client, temp_config_string_rate):
        """/api/submit/weekly must succeed when rate is stored as a string."""
        _, config_path, _ = temp_config_string_rate

        payload = {
            "hours": {"Monday": 8, "Tuesday": 8, "Wednesday": 8, "Thursday": 8,
                      "Friday": 8, "Saturday": 0, "Sunday": 0},
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "week": {
                "start": "March 24",
                "end": "March 30, 2026",
                "invNum": "INV-20260324",
                "dayDates": {}
            },
            "template": "morning-light"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/weekly',
                        json=payload,
                        content_type='application/json'
                    )

                    assert response.status_code == 200, response.get_json()
                    assert response.get_json()['success'] is True

    def test_submit_monthly_with_string_rate(self, client, temp_config_string_rate):
        """/api/submit/monthly must succeed when rate is stored as a string."""
        _, config_path, _ = temp_config_string_rate

        payload = {
            "weekData": [
                {"label": "Mar 3 – Mar 9, 2026", "hours": 40},
                {"label": "Mar 10 – Mar 16, 2026", "hours": 40},
            ],
            "year": 2026,
            "month": 3,
            "accountantEmail": "accountant@example.com"
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_monthly_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/monthly',
                        json=payload,
                        content_type='application/json'
                    )

                    assert response.status_code == 200, response.get_json()
                    assert response.get_json()['success'] is True


class TestSubmitWeeklyWithLogsEndpoint:
    """
    Tests for POST /api/submit/weekly-with-logs.

    This endpoint reads an already-saved invoice PDF, generates the weekly
    log PDF, and emails both as attachments. Previously had no test
    coverage at all — the rate-as-string bug shipped to production because
    of that gap.
    """

    @staticmethod
    def _make_invoice_pdf_on_disk(tmpdir, inv_num="INV-20260323"):
        weekly_dir = os.path.join(tmpdir, 'weekly')
        os.makedirs(weekly_dir, exist_ok=True)
        path = os.path.join(weekly_dir, f"{inv_num}.pdf")
        Path(path).write_bytes(b'%PDF-1.4 existing invoice')
        return path

    def test_weekly_with_logs_success(self, client, temp_config):
        """Happy path: invoice exists, log renders, both emailed."""
        tmpdir, config_path, _ = temp_config
        self._make_invoice_pdf_on_disk(tmpdir, "INV-20260323")

        payload = {
            "invNum": "INV-20260323",
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "hours": {"Monday": 8, "Tuesday": 8, "Wednesday": 8,
                      "Thursday": 8, "Friday": 8},
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_log_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 log content'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/weekly-with-logs',
                        json=payload,
                        content_type='application/json'
                    )

                    assert response.status_code == 200, response.get_json()
                    data = response.get_json()
                    assert data['success'] is True
                    assert data['sent'] == ["client@example.com", "accountant@example.com"]
                    call_kwargs = mock_email.call_args[1]
                    attachments = call_kwargs['attachments']
                    assert len(attachments) == 2
                    assert any('LOG' in a['filename'] for a in attachments)

    def test_weekly_with_logs_string_rate_regression(self, client, temp_config_string_rate):
        """
        REGRESSION: this is the exact bug Lisa hit on 2026-04-11.

        The endpoint loaded config raw (without coercing rate to float)
        and then computed `total_hours * config.get('rate', 0)`. With
        rate stored as the string "25" this raised
        "can't multiply sequence by non-int of type 'float'" and the
        invoice never got sent.
        """
        tmpdir, config_path, _ = temp_config_string_rate
        self._make_invoice_pdf_on_disk(tmpdir, "INV-20260323")

        payload = {
            "invNum": "INV-20260323",
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "hours": {"Monday": 8, "Tuesday": 8, "Wednesday": 8,
                      "Thursday": 8, "Friday": 8},
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            with patch('app.api.submit_api.render_weekly_log_pdf') as mock_pdf:
                with patch('app.api.submit_api.send_invoice_email') as mock_email:
                    mock_pdf.return_value = b'%PDF-1.4 log content'
                    mock_email.return_value = {"success": True}

                    response = client.post(
                        '/api/submit/weekly-with-logs',
                        json=payload,
                        content_type='application/json'
                    )

                    # Before the fix this returned 500 with
                    # "Internal server error".
                    assert response.status_code == 200, response.get_json()
                    assert response.get_json()['success'] is True

    def test_weekly_with_logs_invoice_missing(self, client, temp_config):
        """Returns 400 with a clear message when invoice PDF doesn't exist."""
        _, config_path, _ = temp_config

        payload = {
            "invNum": "INV-20260323",
            "clientEmail": "client@example.com",
            "hours": {"Monday": 8},
        }

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            response = client.post(
                '/api/submit/weekly-with-logs',
                json=payload,
                content_type='application/json'
            )

            assert response.status_code == 400
            assert "Invoice PDF not found" in response.get_json()['error']

    def test_weekly_with_logs_invalid_inv_num(self, client, temp_config):
        """Rejects malformed invoice numbers."""
        _, config_path, _ = temp_config

        with patch('app.api.submit_api.get_config_path', return_value=config_path):
            response = client.post(
                '/api/submit/weekly-with-logs',
                json={"invNum": "not-an-invoice-number"},
                content_type='application/json'
            )

            assert response.status_code == 400


class TestStaticAssetsStartupCheck:
    """
    Tests for the startup self-test that prevents broken bundles from
    leaving users stranded on a JSON error page.
    """

    def test_verify_static_assets_exits_when_index_missing(self, monkeypatch, tmp_path):
        """_verify_static_assets_or_exit must sys.exit when index.html is missing."""
        from app import main as main_mod

        # Point DIST_FOLDER at an empty directory (no index.html).
        empty = tmp_path / "empty_dist"
        empty.mkdir()
        monkeypatch.setattr(main_mod, "DIST_FOLDER", str(empty))

        with pytest.raises(SystemExit) as exc_info:
            main_mod._verify_static_assets_or_exit()
        assert exc_info.value.code == 2

    def test_verify_static_assets_passes_when_index_present(self, monkeypatch, tmp_path):
        """_verify_static_assets_or_exit must NOT exit when index.html exists."""
        from app import main as main_mod

        good = tmp_path / "good_dist"
        good.mkdir()
        (good / "index.html").write_text("<html>ok</html>")
        monkeypatch.setattr(main_mod, "DIST_FOLDER", str(good))

        # Should not raise
        main_mod._verify_static_assets_or_exit()
