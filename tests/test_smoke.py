"""Smoke test: the package imports and exposes a version string."""

from __future__ import annotations

import mika


def test_version_is_present() -> None:
    assert isinstance(mika.__version__, str)
    assert mika.__version__
