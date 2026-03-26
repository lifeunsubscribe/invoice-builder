"""
Pytest configuration for test discovery and imports.

This conftest.py ensures that the app module is importable without
requiring sys.path manipulation in individual test files.
"""

import os
import sys

# Add project root to Python path for test imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
