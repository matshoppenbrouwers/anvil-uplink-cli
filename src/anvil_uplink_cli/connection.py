"""Uplink connection lifecycle — context manager around anvil.server.connect/disconnect."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress

import anvil.server

from anvil_uplink_cli.config import Profile, resolve_key


@contextmanager
def uplink(profile: Profile, explicit_key: str | None = None) -> Iterator[None]:
    """Connect on enter, disconnect on exit. Always disconnects, even on error.

    The key is resolved lazily inside the context so that key resolution errors
    surface as AuthError (not as a generic connect failure). Disconnect errors
    are suppressed during teardown so cleanup never masks the real error.
    """
    key = resolve_key(profile, explicit_key)
    anvil.server.connect(key, url=profile.url, quiet=True)
    try:
        yield
    finally:
        with suppress(Exception):
            anvil.server.disconnect()
