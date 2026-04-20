"""Tests for connection.uplink context manager (mocks anvil.server)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from anvil_uplink_cli.config import Profile
from anvil_uplink_cli.connection import uplink


def test_uplink_connects_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANVIL_BRIDGE_KEY", raising=False)
    with (
        patch("anvil.server.connect") as mock_connect,
        patch("anvil.server.disconnect") as mock_disconnect,
    ):
        p = Profile(name="x", key_ref="env:TEST_KEY")
        monkeypatch.setenv("TEST_KEY", "abc123")
        with uplink(p):
            mock_connect.assert_called_once()
            args, kwargs = mock_connect.call_args
            assert args[0] == "abc123"
            assert kwargs["url"] == p.url
            assert kwargs["quiet"] is True
            mock_disconnect.assert_not_called()
        mock_disconnect.assert_called_once()


def test_uplink_disconnects_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_KEY", "abc123")
    with (
        patch("anvil.server.connect"),
        patch("anvil.server.disconnect") as mock_disconnect,
    ):
        p = Profile(name="x", key_ref="env:TEST_KEY")
        with pytest.raises(RuntimeError, match="boom"), uplink(p):
            raise RuntimeError("boom")
        mock_disconnect.assert_called_once()


def test_uplink_explicit_key_bypasses_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANVIL_BRIDGE_KEY", raising=False)
    with (
        patch("anvil.server.connect") as mock_connect,
        patch("anvil.server.disconnect"),
    ):
        p = Profile(name="x", key_ref="env:MISSING")
        with uplink(p, explicit_key="override"):
            pass
        args, _ = mock_connect.call_args
        assert args[0] == "override"


def test_uplink_suppresses_disconnect_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_KEY", "abc")
    with (
        patch("anvil.server.connect"),
        patch("anvil.server.disconnect", side_effect=RuntimeError("ws already gone")),
    ):
        p = Profile(name="x", key_ref="env:TEST_KEY")
        # Should NOT raise — disconnect errors are swallowed during teardown
        entered = False
        with uplink(p):
            entered = True
        assert entered
