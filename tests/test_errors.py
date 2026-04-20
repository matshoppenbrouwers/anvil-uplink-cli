"""Tests for errors.map_exception and exit code mapping."""
from __future__ import annotations

import pytest

from anvil_uplink_cli import errors


@pytest.mark.parametrize(
    ("exc_cls_attr", "expected_exit"),
    [
        ("UplinkDisconnectedError", errors.EXIT_DISCONNECTED),
        ("AnvilTimeoutError", errors.EXIT_TIMEOUT),
        ("NoServerFunctionError", errors.EXIT_NO_FUNCTION),
        ("SerializationError", errors.EXIT_SERIALIZATION),
        ("PermissionDenied", errors.EXIT_PERMISSION),
        ("QuotaExceededError", errors.EXIT_QUOTA),
        ("InvalidResponseError", errors.EXIT_INVALID_RESPONSE),
        ("RuntimeUnavailableError", errors.EXIT_RUNTIME_UNAVAILABLE),
        ("InternalError", errors.EXIT_INTERNAL),
    ],
)
def test_known_exceptions_map_to_expected_codes(exc_cls_attr: str, expected_exit: int) -> None:
    exc_cls = getattr(errors, exc_cls_attr)
    if exc_cls is None:
        pytest.skip(f"{exc_cls_attr} not present in installed anvil-uplink version")
    # Some anvil exception classes require positional args — try a few patterns.
    try:
        exc = exc_cls("boom")
    except TypeError:
        try:
            exc = exc_cls()
        except TypeError:
            pytest.skip(f"cannot construct {exc_cls_attr} in test environment")
    mapped = errors.map_exception(exc)
    assert mapped.exit_code == expected_exit
    assert mapped.message  # non-empty


def test_anvil_wrapped_error_reports_wrapped_type() -> None:
    if errors.AnvilWrappedError is None:
        pytest.skip("AnvilWrappedError not available")
    try:
        exc = errors.AnvilWrappedError("inner detail")
    except TypeError:
        pytest.skip("AnvilWrappedError requires different construction")
    exc.type = "ValueError"  # type: ignore[attr-defined]
    mapped = errors.map_exception(exc)
    assert mapped.exit_code == errors.EXIT_SERVER_RAISED
    assert "ValueError" in mapped.message


def test_unknown_exception_falls_through() -> None:
    class Weird(Exception):
        pass

    mapped = errors.map_exception(Weird("hello"))
    assert mapped.exit_code == errors.EXIT_UNEXPECTED
    assert "Weird" in mapped.message
    assert "hello" in mapped.message


def test_auth_and_config_errors_exist() -> None:
    # These are raised by config/connection code, not caught by map_exception.
    assert issubclass(errors.AuthError, RuntimeError)
    assert issubclass(errors.ConfigError, RuntimeError)
