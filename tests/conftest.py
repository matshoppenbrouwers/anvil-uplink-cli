"""Shared test fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect platformdirs user_config_dir to a temp location."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path
