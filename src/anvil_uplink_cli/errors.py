"""Map anvil-uplink exceptions to CLI exit codes and user-friendly messages.

Importing this module imports all known exception classes from `anvil.server`
so that callers can catch them via `KNOWN_EXCEPTIONS`. If a future version of
anvil-uplink renames or removes one of these classes, the `_safe_import`
helper makes the failure graceful rather than crashing the CLI at import.
"""
from __future__ import annotations

from dataclasses import dataclass

import anvil.server as _anvil_server


def _safe_import(name: str) -> type[BaseException] | None:
    cls = getattr(_anvil_server, name, None)
    if isinstance(cls, type) and issubclass(cls, BaseException):
        return cls
    return None


UplinkDisconnectedError = _safe_import("UplinkDisconnectedError")
AnvilWrappedError = _safe_import("AnvilWrappedError")
InternalError = _safe_import("InternalError")
NoServerFunctionError = _safe_import("NoServerFunctionError")
SerializationError = _safe_import("SerializationError")
PermissionDenied = _safe_import("PermissionDenied")
QuotaExceededError = _safe_import("QuotaExceededError")
InvalidResponseError = _safe_import("InvalidResponseError")
RuntimeUnavailableError = _safe_import("RuntimeUnavailableError")
# anvil.server.TimeoutError shadows the builtin; keep both addressable
AnvilTimeoutError = _safe_import("TimeoutError")


# CLI exit codes. Reserved:
#   0    success
#   1    generic unexpected error
#   2    usage error (typer-managed)
#   10+  connection / transport
#   20+  protocol / API
#   30+  server-side
#   40+  auth / config
EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_USAGE = 2
EXIT_DISCONNECTED = 10
EXIT_TIMEOUT = 11
EXIT_NO_FUNCTION = 20
EXIT_SERIALIZATION = 21
EXIT_PERMISSION = 22
EXIT_QUOTA = 23
EXIT_INVALID_RESPONSE = 24
EXIT_RUNTIME_UNAVAILABLE = 25
EXIT_SERVER_RAISED = 30
EXIT_INTERNAL = 31
EXIT_AUTH = 40
EXIT_CONFIG = 41
EXIT_IMPERSONATION = 42


@dataclass(frozen=True)
class Mapped:
    exit_code: int
    message: str


def _cls_to_mapping(exc: BaseException) -> Mapped | None:
    t = type(exc)
    msg = str(exc) or t.__name__
    if UplinkDisconnectedError and isinstance(exc, UplinkDisconnectedError):
        return Mapped(EXIT_DISCONNECTED, f"connection lost: {msg}")
    if AnvilTimeoutError and isinstance(exc, AnvilTimeoutError):
        return Mapped(EXIT_TIMEOUT, f"call timed out: {msg}")
    if NoServerFunctionError and isinstance(exc, NoServerFunctionError):
        return Mapped(EXIT_NO_FUNCTION, f"no server function: {msg}")
    if SerializationError and isinstance(exc, SerializationError):
        return Mapped(EXIT_SERIALIZATION, f"cannot serialize: {msg}")
    if PermissionDenied and isinstance(exc, PermissionDenied):
        return Mapped(
            EXIT_PERMISSION,
            f"permission denied: {msg} "
            "(hint: Server Uplink needed for direct Data Table access)",
        )
    if QuotaExceededError and isinstance(exc, QuotaExceededError):
        return Mapped(EXIT_QUOTA, f"app quota exceeded: {msg}")
    if InvalidResponseError and isinstance(exc, InvalidResponseError):
        return Mapped(EXIT_INVALID_RESPONSE, f"invalid response from server: {msg}")
    if RuntimeUnavailableError and isinstance(exc, RuntimeUnavailableError):
        return Mapped(EXIT_RUNTIME_UNAVAILABLE, f"Anvil runtime unavailable: {msg}")
    if AnvilWrappedError and isinstance(exc, AnvilWrappedError):
        wrapped_type = getattr(exc, "type", t.__name__)
        return Mapped(EXIT_SERVER_RAISED, f"server raised {wrapped_type}: {msg}")
    if InternalError and isinstance(exc, InternalError):
        return Mapped(EXIT_INTERNAL, f"Anvil internal error: {msg}")
    return None


def map_exception(exc: BaseException) -> Mapped:
    """Map an exception to an (exit_code, message) pair.

    Falls back to EXIT_UNEXPECTED for unknown exceptions.
    """
    mapped = _cls_to_mapping(exc)
    if mapped is not None:
        return mapped
    return Mapped(EXIT_UNEXPECTED, f"unexpected error: {type(exc).__name__}: {exc}")


class AuthError(RuntimeError):
    """Raised when a key is rejected or missing."""


class ConfigError(RuntimeError):
    """Raised when configuration is malformed or a profile is missing."""


class ImpersonationError(RuntimeError):
    """Raised when CLI-side impersonation setup is invalid.

    Covers the client-side preconditions for --as-user (e.g. the profile
    has no impersonate_secret_ref). Server-side rejections (bad shared
    secret, non-allowlisted email, etc.) still surface as AnvilWrappedError
    and map to EXIT_SERVER_RAISED via map_exception.
    """
