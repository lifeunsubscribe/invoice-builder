"""
Tests for config_api endpoints.

Currently focused on POST /api/config save-side coercion. Validates the
defense added after the rate-as-string production crash so rate is
always written to disk as a number.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from app.main import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def temp_save_folder():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def _post_config(client, payload, save_folder):
    """POST /api/config with get_config_path patched at the read path."""
    config_path = os.path.join(save_folder, 'config.json')
    with patch('app.api.config_api.get_config_path', return_value=config_path):
        # Force the dev-mode branch off so update_config writes to save_folder
        # but doesn't try to also write to a project-root config file.
        with patch('app.api.config_api._dev_base_dir', return_value=save_folder):
            return client.post('/api/config', json=payload, content_type='application/json')


class TestConfigSaveRateCoercion:
    """
    POST /api/config must always store rate as a number on disk.

    The profile form sends rate as a string (it's a text input). Storing
    it as a string used to leak into total_hours * rate math and crash
    the submit endpoints. We coerce on save now so old read-side
    workarounds become a defense in depth, not the primary fix.
    """

    def test_string_rate_is_coerced_to_float(self, client, temp_save_folder):
        payload = {
            "name": "Test User",
            "rate": "25",
            "saveFolder": temp_save_folder,
        }
        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200, resp.get_json()

        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            saved = json.load(f)
        assert isinstance(saved['rate'], float)
        assert saved['rate'] == 25.0

    def test_decimal_string_rate_is_coerced(self, client, temp_save_folder):
        payload = {
            "name": "Test User",
            "rate": "25.50",
            "saveFolder": temp_save_folder,
        }
        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200

        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            saved = json.load(f)
        assert isinstance(saved['rate'], float)
        assert saved['rate'] == 25.5

    def test_garbage_rate_falls_back_to_zero(self, client, temp_save_folder):
        payload = {
            "name": "Test User",
            "rate": "not-a-number",
            "saveFolder": temp_save_folder,
        }
        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200

        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            saved = json.load(f)
        assert saved['rate'] == 0.0

    def test_numeric_rate_passes_through(self, client, temp_save_folder):
        payload = {
            "name": "Test User",
            "rate": 30,
            "saveFolder": temp_save_folder,
        }
        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200

        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            saved = json.load(f)
        assert isinstance(saved['rate'], float)
        assert saved['rate'] == 30.0

    def test_missing_rate_is_left_alone(self, client, temp_save_folder):
        """Coercion only fires when 'rate' is present in the payload."""
        payload = {
            "name": "Test User",
            "saveFolder": temp_save_folder,
        }
        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200

        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            saved = json.load(f)
        assert 'rate' not in saved
