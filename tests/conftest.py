"""
Pytest configuration for test discovery and imports.

This conftest.py ensures that the app module is importable without
requiring sys.path manipulation in individual test files.
"""

import os
import sys
import pytest

# Add project root to Python path for test imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch):
    """
    Disable rate limiting for all tests.

    Rate limiting is important in production but interferes with test execution
    by causing 429 errors when tests run rapidly in sequence.
    """
    from app.middleware.rate_limiter import limiter

    # Disable the limiter by setting enabled=False
    monkeypatch.setattr(limiter, 'enabled', False)
