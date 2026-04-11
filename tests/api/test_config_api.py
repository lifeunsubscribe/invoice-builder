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


def _write_log(save_folder, date_str, meds, client_id="client-1"):
    """Helper: write a daily log file with the given meds list."""
    logs_dir = os.path.join(save_folder, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    fpath = os.path.join(logs_dir, f"LOG-{date_str}.json")
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump({
            "date": date_str,
            "sections": [],
            "meds": meds,
            "clientId": client_id,
        }, f)
    return fpath


def _seed_initial_config(save_folder, meds):
    """Pre-populate config.json with the given meds for client-1."""
    config_path = os.path.join(save_folder, 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump({
            "name": "Test User",
            "saveFolder": save_folder,
            "clients": [
                {
                    "id": "client-1",
                    "name": "Patient",
                    "address": "Addr",
                    "objective": "",
                    "defaultShift": {"start": "09:00", "end": "17:00"},
                    "meds": meds,
                }
            ],
            "activeClientId": "client-1",
        }, f)


class TestMedEditPropagation:
    """
    Regression: Lisa fixed a typo in a med name from Profile and was confused
    that old daily logs still showed the typo. POST /api/config now diffs the
    propagatable med fields (name, dosage, frequency, route) against the
    previous config and rewrites matching meds in every existing daily-log
    JSON file under {saveFolder}/logs/. Per-day fields like `times` are
    preserved.
    """

    def test_typo_fix_propagates_to_old_logs(self, client, temp_save_folder):
        # Initial state: med with a typo
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantnie", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        # An old log with that med, and per-day times the user already entered
        log_path = _write_log(temp_save_folder, "2026-04-01", [
            {"id": "med-1", "name": "Memantnie", "dosage": "10mg",
             "frequency": "daily", "route": "Oral",
             "times": ["08:30", "20:00"]},
        ])

        # User fixes the typo in profile
        new_payload = {
            "name": "Test User",
            "saveFolder": temp_save_folder,
            "clients": [
                {
                    "id": "client-1",
                    "name": "Patient",
                    "address": "Addr",
                    "objective": "",
                    "defaultShift": {"start": "09:00", "end": "17:00"},
                    "meds": [
                        {"id": "med-1", "name": "Memantine", "dosage": "10mg",
                         "frequency": "daily", "route": "Oral"},
                    ],
                }
            ],
            "activeClientId": "client-1",
        }
        resp = _post_config(client, new_payload, temp_save_folder)
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body.get('medLogsUpdated') == 1

        with open(log_path, 'r') as f:
            updated_log = json.load(f)
        assert updated_log['meds'][0]['name'] == 'Memantine'  # typo fixed
        assert updated_log['meds'][0]['times'] == ["08:30", "20:00"]  # preserved

    def test_dosage_change_propagates(self, client, temp_save_folder):
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantine", "dosage": "5mg",
             "frequency": "daily", "route": "Oral"},
        ])
        log_path = _write_log(temp_save_folder, "2026-04-02", [
            {"id": "med-1", "name": "Memantine", "dosage": "5mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])

        new_payload = {
            "name": "Test User", "saveFolder": temp_save_folder,
            "clients": [{
                "id": "client-1", "name": "Patient", "address": "", "objective": "",
                "defaultShift": {"start": "09:00", "end": "17:00"},
                "meds": [{"id": "med-1", "name": "Memantine", "dosage": "10mg",
                          "frequency": "daily", "route": "Oral"}],
            }],
            "activeClientId": "client-1",
        }
        resp = _post_config(client, new_payload, temp_save_folder)
        assert resp.status_code == 200
        assert resp.get_json().get('medLogsUpdated') == 1

        with open(log_path, 'r') as f:
            updated = json.load(f)
        assert updated['meds'][0]['dosage'] == '10mg'

    def test_no_change_no_propagation(self, client, temp_save_folder):
        """Saving an unchanged config must NOT touch any log files."""
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        log_path = _write_log(temp_save_folder, "2026-04-03", [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])
        original_mtime = os.path.getmtime(log_path)

        # Save the same payload back
        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            payload = json.load(f)

        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'medLogsUpdated' not in body

        # File should not have been rewritten
        assert os.path.getmtime(log_path) == original_mtime

    def test_new_med_does_not_backfill(self, client, temp_save_folder):
        """
        Adding a NEW med in profile must NOT inject it into old logs —
        the patient wasn't being given that med then.
        """
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        log_path = _write_log(temp_save_folder, "2026-04-04", [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])

        new_payload = {
            "name": "Test User", "saveFolder": temp_save_folder,
            "clients": [{
                "id": "client-1", "name": "Patient", "address": "", "objective": "",
                "defaultShift": {"start": "09:00", "end": "17:00"},
                "meds": [
                    {"id": "med-1", "name": "Memantine", "dosage": "10mg",
                     "frequency": "daily", "route": "Oral"},
                    {"id": "med-2", "name": "Aspirin", "dosage": "81mg",
                     "frequency": "daily", "route": "Oral"},
                ],
            }],
            "activeClientId": "client-1",
        }
        resp = _post_config(client, new_payload, temp_save_folder)
        assert resp.status_code == 200
        # No propagation since the only changed-by-id med is new
        assert 'medLogsUpdated' not in resp.get_json()

        with open(log_path, 'r') as f:
            updated = json.load(f)
        assert len(updated['meds']) == 1  # still just the original med
        assert updated['meds'][0]['id'] == 'med-1'

    def test_deleted_med_left_in_old_logs(self, client, temp_save_folder):
        """
        Removing a med from profile must NOT delete it from old logs —
        it WAS administered then. Historical accuracy wins.
        """
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
            {"id": "med-2", "name": "Aspirin", "dosage": "81mg",
             "frequency": "daily", "route": "Oral"},
        ])
        log_path = _write_log(temp_save_folder, "2026-04-05", [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
            {"id": "med-2", "name": "Aspirin", "dosage": "81mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])

        new_payload = {
            "name": "Test User", "saveFolder": temp_save_folder,
            "clients": [{
                "id": "client-1", "name": "Patient", "address": "", "objective": "",
                "defaultShift": {"start": "09:00", "end": "17:00"},
                "meds": [
                    {"id": "med-1", "name": "Memantine", "dosage": "10mg",
                     "frequency": "daily", "route": "Oral"},
                ],  # med-2 removed
            }],
            "activeClientId": "client-1",
        }
        resp = _post_config(client, new_payload, temp_save_folder)
        assert resp.status_code == 200
        assert 'medLogsUpdated' not in resp.get_json()

        with open(log_path, 'r') as f:
            updated = json.load(f)
        assert len(updated['meds']) == 2  # both still present
        ids = [m['id'] for m in updated['meds']]
        assert 'med-2' in ids

    def test_propagation_across_multiple_log_files(self, client, temp_save_folder):
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "old name", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        # Three log files spanning different dates, all with med-1
        for d in ("2026-04-01", "2026-04-02", "2026-04-03"):
            _write_log(temp_save_folder, d, [
                {"id": "med-1", "name": "old name", "dosage": "10mg",
                 "frequency": "daily", "route": "Oral", "times": ["08:00"]},
            ])

        new_payload = {
            "name": "Test User", "saveFolder": temp_save_folder,
            "clients": [{
                "id": "client-1", "name": "Patient", "address": "", "objective": "",
                "defaultShift": {"start": "09:00", "end": "17:00"},
                "meds": [{"id": "med-1", "name": "new name", "dosage": "10mg",
                          "frequency": "daily", "route": "Oral"}],
            }],
            "activeClientId": "client-1",
        }
        resp = _post_config(client, new_payload, temp_save_folder)
        assert resp.status_code == 200
        assert resp.get_json().get('medLogsUpdated') == 3

        for d in ("2026-04-01", "2026-04-02", "2026-04-03"):
            with open(os.path.join(temp_save_folder, 'logs', f'LOG-{d}.json'), 'r') as f:
                log = json.load(f)
            assert log['meds'][0]['name'] == 'new name'

    def test_stale_logs_get_fixed_on_unrelated_save(self, client, temp_save_folder):
        """
        REGRESSION (Lisa, 2026-04-11 evening): she fixed a med typo in
        Profile BEFORE the propagator existed, so the on-disk config
        already had the corrected name but old logs still showed the typo.
        On the first version with the propagator, saving the same config
        again with no diff was a no-op (the diff-based propagator only
        fired on actual changes between old and new config).

        The convergent sync makes any subsequent save reconcile log meds
        to the current config — even when there's no diff, even when the
        save is unrelated (e.g. just updating the rate or address).
        """
        # Config already has the corrected name
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        # But the old log still has the typo (wasn't propagated when fix happened)
        log_path = _write_log(temp_save_folder, "2026-04-08", [
            {"id": "med-1", "name": "Memantnie", "dosage": "10mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])

        # User saves an unrelated change (e.g. updates address)
        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            payload = json.load(f)
        payload['address'] = 'New Street 123'

        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200
        body = resp.get_json()
        # The convergent sync should still find the stale log and fix it
        assert body.get('medLogsUpdated') == 1

        with open(log_path, 'r') as f:
            updated = json.load(f)
        assert updated['meds'][0]['name'] == 'Memantine'  # typo finally fixed
        assert updated['meds'][0]['times'] == ["08:00"]  # times preserved

    def test_already_synced_save_is_noop(self, client, temp_save_folder):
        """
        Saving when logs are already in sync with config must NOT rewrite
        any files. Verifies the convergent sync's no-op fast path.
        """
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        log_path = _write_log(temp_save_folder, "2026-04-09", [
            {"id": "med-1", "name": "Memantine", "dosage": "10mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])
        original_mtime = os.path.getmtime(log_path)

        with open(os.path.join(temp_save_folder, 'config.json'), 'r') as f:
            payload = json.load(f)
        payload['address'] = 'Whatever Drive 99'  # unrelated change

        resp = _post_config(client, payload, temp_save_folder)
        assert resp.status_code == 200
        # Convergent sync ran but had nothing to do — no files rewritten
        assert 'medLogsUpdated' not in resp.get_json()
        assert os.path.getmtime(log_path) == original_mtime

    def test_log_with_only_configuredId_still_matches(self, client, temp_save_folder):
        """
        Older logs may have stored meds with `configuredId` instead of `id`.
        The propagator must match either field so historical entries get fixed too.
        """
        _seed_initial_config(temp_save_folder, [
            {"id": "med-1", "name": "old name", "dosage": "10mg",
             "frequency": "daily", "route": "Oral"},
        ])
        log_path = _write_log(temp_save_folder, "2026-03-15", [
            {"configuredId": "med-1", "name": "old name", "dosage": "10mg",
             "frequency": "daily", "route": "Oral", "times": ["08:00"]},
        ])

        new_payload = {
            "name": "Test User", "saveFolder": temp_save_folder,
            "clients": [{
                "id": "client-1", "name": "Patient", "address": "", "objective": "",
                "defaultShift": {"start": "09:00", "end": "17:00"},
                "meds": [{"id": "med-1", "name": "new name", "dosage": "10mg",
                          "frequency": "daily", "route": "Oral"}],
            }],
            "activeClientId": "client-1",
        }
        resp = _post_config(client, new_payload, temp_save_folder)
        assert resp.status_code == 200
        assert resp.get_json().get('medLogsUpdated') == 1

        with open(log_path, 'r') as f:
            updated = json.load(f)
        assert updated['meds'][0]['name'] == 'new name'
