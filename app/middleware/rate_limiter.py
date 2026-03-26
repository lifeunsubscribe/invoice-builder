"""
Rate limiting middleware using Flask-Limiter.

Implements rate limits to prevent DoS attacks:
- Global default: 100 requests per minute per IP
- Submit endpoints: 10 requests per minute per IP (stricter for expensive operations)
- Scan endpoints: 50 requests per minute per IP

Uses in-memory storage (no Redis dependency) suitable for desktop applications.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def get_rate_limiter():
    """
    Create and configure Flask-Limiter instance.

    Returns:
        Limiter: Configured Flask-Limiter instance with in-memory storage
    """
    # Use in-memory storage (no Redis required for desktop app)
    # Key function: get_remote_address for per-IP rate limiting
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        default_limits=["100 per minute"],  # Global default rate limit
        storage_options={}
    )

    return limiter


# Rate limit decorators for specific endpoint categories
SUBMIT_RATE_LIMIT = "10 per minute"  # Stricter limit for expensive PDF generation
SCAN_RATE_LIMIT = "50 per minute"    # Moderate limit for file system operations
