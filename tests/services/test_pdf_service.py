"""
Tests for PDF service validation.

These tests verify that required template variables are properly validated
before rendering, preventing cryptic Jinja2 errors in production.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Import path setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.pdf_service import (
    _validate_config,
    render_weekly_pdf,
    render_monthly_pdf
)


class TestValidateConfig:
    """Tests for the _validate_config helper function."""

    def test_validate_config_all_keys_present(self):
        """Test that validation passes when all required keys are present."""
        config = {
            'name': 'Test User',
            'address': '123 Test St',
            'rate': 25.0
        }
        required_keys = ['name', 'address', 'rate']

        # Should not raise
        _validate_config(config, required_keys)

    def test_validate_config_single_missing_key(self):
        """Test that validation fails with clear message for single missing key."""
        config = {
            'name': 'Test User',
            'address': '123 Test St'
        }
        required_keys = ['name', 'address', 'rate']

        with pytest.raises(ValueError) as exc_info:
            _validate_config(config, required_keys)

        assert "Missing required config keys: rate" in str(exc_info.value)

    def test_validate_config_multiple_missing_keys(self):
        """Test that validation reports all missing keys at once."""
        config = {
            'name': 'Test User'
        }
        required_keys = ['name', 'address', 'rate', 'clientName']

        with pytest.raises(ValueError) as exc_info:
            _validate_config(config, required_keys)

        error_message = str(exc_info.value)
        assert "Missing required config keys:" in error_message
        assert "address" in error_message
        assert "rate" in error_message
        assert "clientName" in error_message

    def test_validate_config_empty_config(self):
        """Test that validation fails for empty config dict."""
        config = {}
        required_keys = ['name', 'address']

        with pytest.raises(ValueError) as exc_info:
            _validate_config(config, required_keys)

        error_message = str(exc_info.value)
        assert "name" in error_message
        assert "address" in error_message

    def test_validate_config_extra_keys_allowed(self):
        """Test that extra keys in config are allowed (no error)."""
        config = {
            'name': 'Test User',
            'address': '123 Test St',
            'rate': 25.0,
            'extraKey': 'extra value',
            'anotherExtra': 123
        }
        required_keys = ['name', 'address', 'rate']

        # Should not raise
        _validate_config(config, required_keys)


class TestRenderWeeklyPdf:
    """Tests for render_weekly_pdf validation."""

    @pytest.fixture
    def valid_weekly_config(self):
        """Fixture providing a valid weekly invoice config."""
        return {
            'name': 'Lisa Wadley',
            'address': '123 Main St, Denver, CO 80201',
            'personalEmail': 'lisa@email.com',
            'rate': 28.00,
            'clientName': 'Sunrise Home Health Agency',
            'clientEmail': 'billing@sunrisehh.com',
            'invoiceNote': 'Thank you for the privilege of caring for your clients.'
        }

    @pytest.fixture
    def valid_hours(self):
        """Fixture providing valid hours dict."""
        return {
            'Monday': 8,
            'Tuesday': 8,
            'Wednesday': 8,
            'Thursday': 8,
            'Friday': 8,
            'Saturday': 0,
            'Sunday': 0
        }

    @pytest.fixture
    def valid_week(self):
        """Fixture providing valid week metadata."""
        return {
            'start': 'March 24',
            'end': 'March 30, 2026',
            'invNum': 'INV-20260324',
            'dayDates': {
                'Monday': 'Mar 24',
                'Tuesday': 'Mar 25',
                'Wednesday': 'Mar 26',
                'Thursday': 'Mar 27',
                'Friday': 'Mar 28',
                'Saturday': 'Mar 29',
                'Sunday': 'Mar 30'
            }
        }

    def test_render_weekly_pdf_missing_name(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'name' raises ValueError."""
        del valid_weekly_config['name']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: name" in str(exc_info.value)

    def test_render_weekly_pdf_missing_address(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'address' raises ValueError."""
        del valid_weekly_config['address']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: address" in str(exc_info.value)

    def test_render_weekly_pdf_missing_personal_email(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'personalEmail' raises ValueError."""
        del valid_weekly_config['personalEmail']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: personalEmail" in str(exc_info.value)

    def test_render_weekly_pdf_missing_rate(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'rate' raises ValueError."""
        del valid_weekly_config['rate']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: rate" in str(exc_info.value)

    def test_render_weekly_pdf_missing_client_name(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'clientName' raises ValueError."""
        del valid_weekly_config['clientName']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: clientName" in str(exc_info.value)

    def test_render_weekly_pdf_missing_client_email(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'clientEmail' raises ValueError."""
        del valid_weekly_config['clientEmail']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: clientEmail" in str(exc_info.value)

    def test_render_weekly_pdf_missing_invoice_note(self, valid_weekly_config, valid_hours, valid_week):
        """Test that missing 'invoiceNote' raises ValueError."""
        del valid_weekly_config['invoiceNote']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        assert "Missing required config keys: invoiceNote" in str(exc_info.value)

    def test_render_weekly_pdf_multiple_missing_keys(self, valid_weekly_config, valid_hours, valid_week):
        """Test that multiple missing keys are all reported."""
        del valid_weekly_config['name']
        del valid_weekly_config['rate']
        del valid_weekly_config['clientEmail']

        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'morning-light')

        error_message = str(exc_info.value)
        assert "name" in error_message
        assert "rate" in error_message
        assert "clientEmail" in error_message

    def test_render_weekly_pdf_invalid_template_id(self, valid_weekly_config, valid_hours, valid_week):
        """Test that invalid template_id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, 'invalid-template')

        assert "Invalid template_id 'invalid-template'" in str(exc_info.value)

    @patch('app.services.pdf_service.HTML')
    @patch('app.services.pdf_service._get_jinja_env')
    def test_render_weekly_pdf_valid_config_all_templates(
        self, mock_jinja_env, mock_html, valid_weekly_config, valid_hours, valid_week
    ):
        """Test that valid config passes validation for all template variants."""
        # Mock Jinja environment and template
        mock_template = MagicMock()
        mock_template.render.return_value = '<html>Test</html>'
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template
        mock_jinja_env.return_value = mock_env

        # Mock HTML and PDF writing
        mock_pdf = MagicMock()
        mock_pdf.write_pdf.return_value = None
        mock_html.return_value = mock_pdf

        # Test all three template variants
        for template_id in ['morning-light', 'caring-hands', 'garden']:
            # Should not raise ValueError for validation
            try:
                render_weekly_pdf(valid_weekly_config, valid_hours, valid_week, template_id)
            except ValueError as e:
                if "Missing required config keys" in str(e):
                    pytest.fail(f"Validation failed for {template_id}: {e}")
                # Other ValueErrors (like template loading) are ok for this test


class TestRenderMonthlyPdf:
    """Tests for render_monthly_pdf validation."""

    @pytest.fixture
    def valid_monthly_config(self):
        """Fixture providing a valid monthly report config."""
        return {
            'name': 'Lisa Wadley',
            'address': '123 Main St, Denver, CO 80201',
            'personalEmail': 'lisa@email.com',
            'rate': 28.00,
            'clientName': 'Sunrise Home Health Agency',
            'clientEmail': 'billing@sunrisehh.com',
            'accountantEmail': 'accountant@cpa.com'
        }

    @pytest.fixture
    def valid_week_data(self):
        """Fixture providing valid week data for monthly report."""
        return [
            {'label': 'Mar 3 – Mar 9', 'hours': 40},
            {'label': 'Mar 10 – Mar 16', 'hours': 40},
            {'label': 'Mar 17 – Mar 23', 'hours': 32},
            {'label': 'Mar 24 – Mar 30', 'hours': 0}
        ]

    def test_render_monthly_pdf_missing_name(self, valid_monthly_config, valid_week_data):
        """Test that missing 'name' raises ValueError."""
        del valid_monthly_config['name']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: name" in str(exc_info.value)

    def test_render_monthly_pdf_missing_address(self, valid_monthly_config, valid_week_data):
        """Test that missing 'address' raises ValueError."""
        del valid_monthly_config['address']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: address" in str(exc_info.value)

    def test_render_monthly_pdf_missing_personal_email(self, valid_monthly_config, valid_week_data):
        """Test that missing 'personalEmail' raises ValueError."""
        del valid_monthly_config['personalEmail']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: personalEmail" in str(exc_info.value)

    def test_render_monthly_pdf_missing_rate(self, valid_monthly_config, valid_week_data):
        """Test that missing 'rate' raises ValueError."""
        del valid_monthly_config['rate']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: rate" in str(exc_info.value)

    def test_render_monthly_pdf_missing_client_name(self, valid_monthly_config, valid_week_data):
        """Test that missing 'clientName' raises ValueError."""
        del valid_monthly_config['clientName']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: clientName" in str(exc_info.value)

    def test_render_monthly_pdf_missing_client_email(self, valid_monthly_config, valid_week_data):
        """Test that missing 'clientEmail' raises ValueError."""
        del valid_monthly_config['clientEmail']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: clientEmail" in str(exc_info.value)

    def test_render_monthly_pdf_missing_accountant_email(self, valid_monthly_config, valid_week_data):
        """Test that missing 'accountantEmail' raises ValueError."""
        del valid_monthly_config['accountantEmail']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        assert "Missing required config keys: accountantEmail" in str(exc_info.value)

    def test_render_monthly_pdf_multiple_missing_keys(self, valid_monthly_config, valid_week_data):
        """Test that multiple missing keys are all reported."""
        del valid_monthly_config['name']
        del valid_monthly_config['rate']
        del valid_monthly_config['accountantEmail']

        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')

        error_message = str(exc_info.value)
        assert "name" in error_message
        assert "rate" in error_message
        assert "accountantEmail" in error_message

    @patch('app.services.pdf_service.HTML')
    @patch('app.services.pdf_service._get_jinja_env')
    def test_render_monthly_pdf_valid_config(
        self, mock_jinja_env, mock_html, valid_monthly_config, valid_week_data
    ):
        """Test that valid config passes validation."""
        # Mock Jinja environment and template
        mock_template = MagicMock()
        mock_template.render.return_value = '<html>Test</html>'
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template
        mock_jinja_env.return_value = mock_env

        # Mock HTML and PDF writing
        mock_pdf = MagicMock()
        mock_pdf.write_pdf.return_value = None
        mock_html.return_value = mock_pdf

        # Should not raise ValueError for validation
        try:
            render_monthly_pdf(valid_monthly_config, valid_week_data, 'March 2026')
        except ValueError as e:
            if "Missing required config keys" in str(e):
                pytest.fail(f"Validation failed: {e}")
            # Other ValueErrors (like template loading) are ok for this test


class TestWeeklyVsMonthlyRequirements:
    """Tests to verify the different requirements for weekly vs monthly reports."""

    @pytest.fixture
    def base_config(self):
        """Config with fields common to both weekly and monthly."""
        return {
            'name': 'Lisa Wadley',
            'address': '123 Main St',
            'personalEmail': 'lisa@email.com',
            'rate': 28.00,
            'clientName': 'Sunrise Home Health',
            'clientEmail': 'billing@sunrise.com'
        }

    @pytest.fixture
    def hours(self):
        """Basic hours dict."""
        return {'Monday': 8, 'Tuesday': 8, 'Wednesday': 0, 'Thursday': 0,
                'Friday': 0, 'Saturday': 0, 'Sunday': 0}

    @pytest.fixture
    def week(self):
        """Basic week dict."""
        return {
            'start': 'Mar 24',
            'end': 'Mar 30, 2026',
            'invNum': 'INV-20260324',
            'dayDates': {}
        }

    @pytest.fixture
    def week_data(self):
        """Basic week data for monthly."""
        return [{'label': 'Mar 3 – Mar 9', 'hours': 40}]

    @patch('app.services.pdf_service.HTML')
    @patch('app.services.pdf_service._get_jinja_env')
    def test_weekly_requires_invoice_note(self, mock_jinja_env, mock_html, base_config, hours, week):
        """Test that weekly invoices require invoiceNote but not accountantEmail."""
        # Weekly should fail without invoiceNote
        with pytest.raises(ValueError) as exc_info:
            render_weekly_pdf(base_config, hours, week, 'morning-light')
        assert "invoiceNote" in str(exc_info.value)

        # Add invoiceNote, should pass validation (though may fail on template loading)
        config_with_note = {**base_config, 'invoiceNote': 'Thank you'}

        mock_template = MagicMock()
        mock_template.render.return_value = '<html>Test</html>'
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template
        mock_jinja_env.return_value = mock_env

        mock_pdf = MagicMock()
        mock_pdf.write_pdf.return_value = None
        mock_html.return_value = mock_pdf

        try:
            render_weekly_pdf(config_with_note, hours, week, 'morning-light')
        except ValueError as e:
            if "Missing required config keys" in str(e):
                pytest.fail(f"Should not fail validation: {e}")

    @patch('app.services.pdf_service.HTML')
    @patch('app.services.pdf_service._get_jinja_env')
    def test_monthly_requires_accountant_email(self, mock_jinja_env, mock_html, base_config, week_data):
        """Test that monthly reports require accountantEmail but not invoiceNote."""
        # Monthly should fail without accountantEmail
        with pytest.raises(ValueError) as exc_info:
            render_monthly_pdf(base_config, week_data, 'March 2026')
        assert "accountantEmail" in str(exc_info.value)

        # Add accountantEmail, should pass validation
        config_with_accountant = {**base_config, 'accountantEmail': 'accountant@cpa.com'}

        mock_template = MagicMock()
        mock_template.render.return_value = '<html>Test</html>'
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template
        mock_jinja_env.return_value = mock_env

        mock_pdf = MagicMock()
        mock_pdf.write_pdf.return_value = None
        mock_html.return_value = mock_pdf

        try:
            render_monthly_pdf(config_with_accountant, week_data, 'March 2026')
        except ValueError as e:
            if "Missing required config keys" in str(e):
                pytest.fail(f"Should not fail validation: {e}")
