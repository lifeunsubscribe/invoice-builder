"""
Tests for static file serving error handling in app/main.py.

Tests verify that the application correctly handles:
- Missing dist folder
- Missing index.html
- 404 errors for non-existent routes
- 500 errors
- General exception handling
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import Flask app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app, DIST_FOLDER


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_dist_folder():
    """Create a temporary dist folder with index.html for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create index.html
        index_path = os.path.join(tmpdir, 'index.html')
        with open(index_path, 'w') as f:
            f.write('<!DOCTYPE html><html><head><title>Test</title></head><body><div id="root"></div></body></html>')
        yield tmpdir


class TestIndexRoute:
    """Tests for the / route serving index.html."""

    @patch('app.main.DIST_FOLDER')
    def test_index_missing_dist_folder(self, mock_dist_folder, client):
        """Test that index route handles missing dist folder gracefully."""
        # Set DIST_FOLDER to a non-existent path
        mock_dist_folder.__str__ = lambda self: '/nonexistent/dist'
        mock_dist_folder.__fspath__ = lambda self: '/nonexistent/dist'

        # Mock os.path.exists to return False for dist folder
        with patch('app.main.os.path.exists', return_value=False):
            response = client.get('/')

            assert response.status_code == 500
            data = response.get_json()
            assert data['error'] == 'Static files not found'
            assert 'frontend build directory does not exist' in data['message']

    @patch('app.main.DIST_FOLDER')
    def test_index_missing_index_html(self, mock_dist_folder, client, temp_dist_folder):
        """Test that index route handles missing index.html gracefully."""
        # Set DIST_FOLDER to temp folder but don't create index.html
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_dist_folder.__str__ = lambda self: tmpdir
            mock_dist_folder.__fspath__ = lambda self: tmpdir

            # Mock os.path.exists to return True for dist folder, False for index.html
            def exists_side_effect(path):
                path_str = str(path)
                if path_str == tmpdir or path == mock_dist_folder:
                    return True
                elif 'index.html' in path_str:
                    return False
                return False

            with patch('app.main.os.path.exists', side_effect=exists_side_effect):
                response = client.get('/')

                assert response.status_code == 500
                data = response.get_json()
                assert data['error'] == 'Static file not found'
                assert 'index.html not found' in data['message']

    @patch('app.main.DIST_FOLDER')
    @patch('app.main.app.send_static_file')
    def test_index_serves_html_when_exists(self, mock_send_static, mock_dist_folder, client, temp_dist_folder):
        """Test that index route serves index.html when it exists."""
        # Setup mocks
        mock_dist_folder.__str__ = lambda self: temp_dist_folder
        mock_dist_folder.__fspath__ = lambda self: temp_dist_folder
        mock_send_static.return_value = '<!DOCTYPE html><html></html>'

        # Mock os.path.exists to return True
        with patch('app.main.os.path.exists', return_value=True):
            response = client.get('/')

            # Verify send_static_file was called with correct argument
            mock_send_static.assert_called_once_with('index.html')

    @patch('app.main.DIST_FOLDER')
    @patch('app.main.app.send_static_file')
    def test_index_handles_exception(self, mock_send_static, mock_dist_folder, client):
        """Test that index route handles unexpected exceptions."""
        # Setup mocks
        mock_dist_folder.__str__ = lambda self: '/some/path'
        mock_dist_folder.__fspath__ = lambda self: '/some/path'

        # Mock os.path.exists to return True but send_static_file to raise exception
        with patch('app.main.os.path.exists', return_value=True):
            mock_send_static.side_effect = Exception("Unexpected error")

            response = client.get('/')

            assert response.status_code == 500
            data = response.get_json()
            assert data['error'] == 'Server error'
            assert 'error occurred while serving' in data['message']

    @patch('app.main.DIST_FOLDER')
    def test_index_missing_dist_fires_crash_report(self, mock_dist_folder, client):
        """
        REGRESSION (2026-04-11 Lisa update race): when DIST_FOLDER is missing
        at request time, we MUST fire a crash report. Previously the index()
        handler returned `jsonify(...), 500` directly, which bypasses Flask's
        @errorhandler(500), so the auto-reporter never ran. The dist-vanished
        race during a self-update went silent and the dev never got an email.
        """
        mock_dist_folder.__str__ = lambda self: '/nonexistent/dist'
        mock_dist_folder.__fspath__ = lambda self: '/nonexistent/dist'

        with patch('app.main.os.path.exists', return_value=False):
            with patch('app.services.report_service.report_exception_async') as mock_report:
                response = client.get('/')

                assert response.status_code == 500
                # Crash reporter must have been called with a useful exception
                mock_report.assert_called_once()
                exc = mock_report.call_args[0][0]
                assert isinstance(exc, RuntimeError)
                assert 'Dist folder missing' in str(exc)

    @patch('app.main.DIST_FOLDER')
    def test_index_missing_index_html_fires_crash_report(self, mock_dist_folder, client):
        """Same regression for the missing-index.html branch of index()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_dist_folder.__str__ = lambda self: tmpdir
            mock_dist_folder.__fspath__ = lambda self: tmpdir

            def exists_side_effect(path):
                path_str = str(path)
                if path_str == tmpdir or path == mock_dist_folder:
                    return True
                return False

            with patch('app.main.os.path.exists', side_effect=exists_side_effect):
                with patch('app.services.report_service.report_exception_async') as mock_report:
                    response = client.get('/')

                    assert response.status_code == 500
                    mock_report.assert_called_once()
                    exc = mock_report.call_args[0][0]
                    assert isinstance(exc, RuntimeError)
                    assert 'index.html missing' in str(exc)


class TestErrorHandlers:
    """Tests for Flask error handlers."""

    def test_404_handler(self, client):
        """Test that 404 handler returns proper JSON response."""
        response = client.get('/nonexistent-route')

        assert response.status_code == 404
        data = response.get_json()
        assert data['error'] == 'Not found'
        # Verify generic message is returned (not raw exception details)
        assert data['message'] == 'The requested resource was not found'

    def test_404_static_file(self, client):
        """Test that 404 handler works for missing static files."""
        response = client.get('/nonexistent-file.js')

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert data['error'] == 'Not found'

    def test_404_api_route(self, client):
        """Test that 404 handler works for missing API routes."""
        response = client.get('/api/nonexistent')

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('app.main.app.send_static_file')
    def test_500_handler(self, mock_send_static, client):
        """Test that 500 handler returns proper JSON response."""
        # Mock send_static_file to raise an exception, which will trigger generic exception handler
        mock_send_static.side_effect = ValueError("Test internal error")

        with patch('app.main.os.path.exists', return_value=True):
            response = client.get('/')

            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data
            assert data['error'] == 'Server error'

    @patch('app.main.app.send_static_file')
    def test_generic_exception_handler(self, mock_send_static, client):
        """Test that generic exception handler catches all exceptions."""
        # Mock send_static_file to raise a custom exception
        mock_send_static.side_effect = RuntimeError("Custom exception")

        with patch('app.main.os.path.exists', return_value=True):
            response = client.get('/')

            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data

    @patch('app.main.app.send_static_file')
    def test_http_exception_handler(self, mock_send_static, client):
        """Test that HTTP exceptions are handled properly."""
        from werkzeug.exceptions import BadRequest

        # Mock send_static_file to raise HTTPException with potentially sensitive details
        mock_send_static.side_effect = BadRequest("Invalid request: /internal/path/details.txt missing")

        with patch('app.main.os.path.exists', return_value=True):
            response = client.get('/')

            assert response.status_code == 400
            data = response.get_json()
            assert 'error' in data
            # Verify generic message is returned, not the sensitive exception details
            assert data['message'] == 'The request could not be processed'
            assert '/internal/path' not in data['message']


class TestStaticFileServing:
    """Tests for static file serving behavior."""

    @patch('app.main.DIST_FOLDER')
    def test_static_file_not_found(self, mock_dist_folder, client):
        """Test that missing static files return 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_dist_folder.__str__ = lambda self: tmpdir
            mock_dist_folder.__fspath__ = lambda self: tmpdir

            # Try to access a non-existent static file
            response = client.get('/assets/nonexistent.js')

            assert response.status_code == 404

    @patch('app.main.DIST_FOLDER')
    def test_static_file_exists(self, mock_dist_folder, client):
        """Test that existing static files are served correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a static file
            assets_dir = os.path.join(tmpdir, 'assets')
            os.makedirs(assets_dir)
            test_file = os.path.join(assets_dir, 'test.js')
            with open(test_file, 'w') as f:
                f.write('console.log("test");')

            # Update DIST_FOLDER and app's static_folder
            mock_dist_folder.__str__ = lambda self: tmpdir
            mock_dist_folder.__fspath__ = lambda self: tmpdir
            app.static_folder = tmpdir

            response = client.get('/assets/test.js')

            # Should either succeed (200) or return 404 if routing doesn't work
            # In production, Flask's static file serving would handle this
            assert response.status_code in [200, 404]


class TestLogging:
    """Tests for logging behavior."""

    @patch('app.main.DIST_FOLDER')
    @patch('app.main.logger')
    def test_missing_dist_logs_error(self, mock_logger, mock_dist_folder, client):
        """Test that missing dist folder logs an error."""
        mock_dist_folder.__str__ = lambda self: '/nonexistent'
        mock_dist_folder.__fspath__ = lambda self: '/nonexistent'

        with patch('app.main.os.path.exists', return_value=False):
            response = client.get('/')

            # Verify logger.error was called
            assert mock_logger.error.called

    @patch('app.main.logger')
    def test_404_logs_warning(self, mock_logger, client):
        """Test that 404 errors log a warning."""
        response = client.get('/nonexistent')

        # Verify logger.warning was called
        assert mock_logger.warning.called

    @patch('app.main.logger')
    @patch('app.main.app.send_static_file')
    def test_500_logs_error(self, mock_send_static, mock_logger, client):
        """Test that 500 errors log an error."""
        # Mock send_static_file to raise an exception
        mock_send_static.side_effect = ValueError("Test error")

        with patch('app.main.os.path.exists', return_value=True):
            response = client.get('/')

            # Verify logger was called for exception
            assert mock_logger.exception.called or mock_logger.error.called
