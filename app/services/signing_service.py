"""
Digital Signature Service

Generates HMAC-SHA256 signatures for monthly reports to prove
authenticity and detect tampering. Uses a locally-stored secret key.

Functions:
    sign_report(report_data) -> dict with signature, fingerprint, timestamp
    verify_signature(report_data, signature_hex) -> bool
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone

# Key file location — stored alongside config.json
KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.signing-key')


def _get_or_create_key():
    """
    Load the signing key from disk, or generate one if it doesn't exist.

    Returns:
        bytes: 32-byte secret key
    """
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
        if len(key) == 32:
            return key

    # Generate a new 256-bit key
    key = secrets.token_bytes(32)
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    return key


def _canonical_data(report_data):
    """
    Create a canonical JSON string from report data for signing.

    Sorts keys to ensure consistent ordering regardless of dict insertion order.

    Args:
        report_data: dict with report fields to sign

    Returns:
        str: deterministic JSON representation
    """
    return json.dumps(report_data, sort_keys=True, separators=(',', ':'))


def sign_report(report_data):
    """
    Sign report data and return signature details.

    Args:
        report_data: dict with fields to sign, e.g.:
            {
                "provider": "Lisa W",
                "month": "March 2026",
                "total_hours": 160,
                "total_pay": "4800.00",
                "weeks": [{"label": "Mar 3 – Mar 9", "hours": 40}, ...]
            }

    Returns:
        dict with:
            - signature: str, full HMAC-SHA256 hex digest (64 chars)
            - fingerprint: str, short display code (first 16 chars, formatted)
            - timestamp: str, ISO 8601 UTC timestamp of signing
            - data_hash: str, SHA-256 hash of the canonical data
    """
    key = _get_or_create_key()
    canonical = _canonical_data(report_data)

    # Hash the canonical data
    data_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    # HMAC-SHA256 sign the data hash
    signature = hmac.new(key, data_hash.encode('utf-8'), hashlib.sha256).hexdigest()

    # Format fingerprint for display: XXXX-XXXX-XXXX-XXXX
    short = signature[:16].upper()
    fingerprint = f"{short[:4]}-{short[4:8]}-{short[8:12]}-{short[12:16]}"

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    return {
        'signature': signature,
        'fingerprint': fingerprint,
        'timestamp': timestamp,
        'data_hash': data_hash
    }


def verify_signature(report_data, signature_hex):
    """
    Verify a signature against report data.

    Args:
        report_data: dict, same structure used when signing
        signature_hex: str, the full HMAC-SHA256 hex digest to verify

    Returns:
        bool: True if signature is valid
    """
    key = _get_or_create_key()
    canonical = _canonical_data(report_data)
    data_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    expected = hmac.new(key, data_hash.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex)
