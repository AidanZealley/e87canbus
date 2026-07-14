"""Compatibility imports for the former simulator API module.

New code should import application composition from :mod:`e87canbus.api.main`.
"""

from e87canbus.api.cli import build_parser, main
from e87canbus.api.internal.websocket import ConnectionManager
from e87canbus.api.main import app, create_app

__all__ = ["ConnectionManager", "app", "build_parser", "create_app", "main"]
