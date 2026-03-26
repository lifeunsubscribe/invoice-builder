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
            "accent": "#b76e79",
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

                    # Verify PDF was saved
                    pdf_path = os.path.join(tmpdir, 'monthly', 'RPT-2026-03.pdf')
                    assert os.path.exists(pdf_path)

                    # Verify render_monthly_pdf was called with correct month label
                    mock_pdf.assert_called_once()
                    call_args = mock_pdf.call_args[1]
                    assert call_args['month_label'] == 'March 2026'
                    assert call_args['week_data'] == payload['weekData']

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
