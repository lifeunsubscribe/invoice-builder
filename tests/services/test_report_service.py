"""
Tests for report_service spool/drain behavior.

The reporter spools failed sends to a local directory and retries them
on the next successful send so an offline crash isn't silently lost.
"""

import json
import os
from unittest.mock import patch

import pytest

from app.services import report_service


@pytest.fixture
def isolated_pending_dir(tmp_path, monkeypatch):
    """Point the spool dir at a fresh tmp dir for each test."""
    pending = tmp_path / "pending-reports"
    monkeypatch.setattr(report_service, 'PENDING_REPORTS_DIR', str(pending))
    return pending


class TestSpoolOnFailure:
    """When SMTP send fails, the report must be persisted to disk."""

    def test_smtp_failure_spools_report(self, isolated_pending_dir):
        with patch.object(
            report_service, '_send_one_email',
            side_effect=ConnectionError("simulated offline"),
        ):
            result = report_service.send_report(
                user_description="something broke",
                error_info={"type": "Boom", "message": "kapow", "traceback": "tb"},
            )

        assert result['success'] is False
        assert 'simulated offline' in result['error']

        # A spooled file should now exist on disk
        files = list(isolated_pending_dir.iterdir())
        assert len(files) == 1
        spooled = json.loads(files[0].read_text())
        assert 'kapow' in spooled['body']
        assert 'CRASH' in spooled['subject']
        assert spooled['sms_text']  # SMS payload preserved
        assert spooled['spooled_at']

    def test_spool_dir_created_lazily(self, tmp_path, monkeypatch):
        """The spool dir doesn't need to pre-exist."""
        nonexistent = tmp_path / "deeply" / "nested" / "pending"
        monkeypatch.setattr(report_service, 'PENDING_REPORTS_DIR', str(nonexistent))

        with patch.object(
            report_service, '_send_one_email',
            side_effect=ConnectionError("offline"),
        ):
            report_service.send_report(error_info={"type": "X", "message": "y", "traceback": ""})

        assert nonexistent.exists()
        assert len(list(nonexistent.iterdir())) == 1


class TestDrainPendingReports:
    """When a live send works, spooled reports must be flushed."""

    def _spool_one(self, pending_dir, name="20260411-090000-deadbeef.json", body="old crash"):
        pending_dir.mkdir(parents=True, exist_ok=True)
        f = pending_dir / name
        f.write_text(json.dumps({
            "subject": "[CRASH] Old report",
            "body": body,
            "sms_text": "alert",
            "spooled_at": "2026-04-10T20:00:00",
        }))
        return f

    def test_drain_resends_and_deletes(self, isolated_pending_dir):
        """Successful drain re-sends the spooled file and removes it."""
        spooled_file = self._spool_one(isolated_pending_dir)

        sent = []

        def _fake_send(addr, pwd, to, subject, body, host, port):
            sent.append({"to": to, "subject": subject, "body": body})
            return True

        with patch(
            'app.services.mail_service._get_smtp_credentials',
            return_value=('user@gmail.com', 'pwd'),
        ):
            with patch.object(report_service, '_send_one_email', side_effect=_fake_send):
                report_service._drain_pending_reports()

        # The retry email should have been sent and the spool file removed.
        assert len(sent) == 1
        assert sent[0]['subject'].startswith('[RETRY]')
        assert 'old crash' in sent[0]['body']
        assert not spooled_file.exists()

    def test_drain_keeps_file_on_failure(self, isolated_pending_dir):
        """If retry send fails, the spool file is left on disk for next launch."""
        spooled_file = self._spool_one(isolated_pending_dir)

        with patch(
            'app.services.mail_service._get_smtp_credentials',
            return_value=('user@gmail.com', 'pwd'),
        ):
            with patch.object(
                report_service, '_send_one_email',
                side_effect=ConnectionError("still offline"),
            ):
                report_service._drain_pending_reports()

        assert spooled_file.exists()  # left on disk for next attempt

    def test_drain_silently_returns_with_no_dir(self, tmp_path, monkeypatch):
        """Missing spool dir is not an error — just nothing to do."""
        monkeypatch.setattr(
            report_service, 'PENDING_REPORTS_DIR', str(tmp_path / "never-created"),
        )
        # Should not raise
        report_service._drain_pending_reports()

    def test_drain_skips_when_credentials_missing(self, isolated_pending_dir):
        """Missing creds means we can't drain — bail without crashing."""
        spooled_file = self._spool_one(isolated_pending_dir)

        with patch(
            'app.services.mail_service._get_smtp_credentials',
            side_effect=RuntimeError("no creds"),
        ):
            report_service._drain_pending_reports()

        assert spooled_file.exists()  # left for retry once creds appear

    def test_successful_send_triggers_drain(self, isolated_pending_dir):
        """A live successful send must opportunistically flush the spool."""
        spooled_file = self._spool_one(isolated_pending_dir, body="prior crash")

        sent = []

        def _fake_send(addr, pwd, to, subject, body, host, port):
            sent.append({"to": to, "subject": subject})
            return True

        with patch(
            'app.services.mail_service._get_smtp_credentials',
            return_value=('user@gmail.com', 'pwd'),
        ):
            with patch.object(report_service, '_send_one_email', side_effect=_fake_send):
                result = report_service.send_report(
                    error_info={"type": "Fresh", "message": "boom", "traceback": ""},
                )

        assert result['success'] is True
        # We sent: live report, SMS, drained retry — total 3.
        assert len(sent) >= 2
        retry_subjects = [s['subject'] for s in sent if s['subject'].startswith('[RETRY]')]
        assert len(retry_subjects) == 1
        assert not spooled_file.exists()
