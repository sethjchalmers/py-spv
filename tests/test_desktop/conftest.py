"""Auto-skip desktop tests when PySide6 is not installed.

CI installs only the ``[dev]`` extras (no Qt).  Tests decorated with
``@pytest.mark.desktop`` are automatically skipped so the rest of the
suite (including theme-only tests in this directory) can still run.
"""

from __future__ import annotations

import importlib

import pytest

_HAS_PYSIDE6 = importlib.util.find_spec("PySide6") is not None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip items carrying the *desktop* marker when PySide6 is absent."""
    if _HAS_PYSIDE6:
        return
    skip = pytest.mark.skip(reason="PySide6 not installed")
    for item in items:
        if item.get_closest_marker("desktop"):
            item.add_marker(skip)
