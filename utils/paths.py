"""
Centralized path utilities for PyInstaller compatibility.

Two kinds of directories:
  - bundle_dir: read-only resources shipped with the app (web/dist, sign.js, proto/)
  - app_dir:    writable directory for user data (config.yaml, audio_cache/, products.json)
"""

import os
import sys


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def get_bundle_dir() -> str:
    """Read-only resources bundled by PyInstaller (web/dist, sign.js, proto/).
    In dev mode, this is the project root."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_dir() -> str:
    """Writable directory next to the executable (config.yaml, audio_cache/).
    In dev mode, this is the project root."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path: str) -> str:
    """Absolute path to a bundled read-only resource."""
    return os.path.join(get_bundle_dir(), relative_path)


def get_data_path(relative_path: str) -> str:
    """Absolute path to a user-writable data file."""
    return os.path.join(get_app_dir(), relative_path)
