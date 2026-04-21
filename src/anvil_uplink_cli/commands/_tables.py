"""Shared helpers for commands that touch `anvil.tables.app_tables`.

Lazy-imports `app_tables` so the cost only lands when a command actually
needs it, and so modules that merely import a command (e.g. `cli.py`)
don't transitively pull `anvil.tables`.
"""
from __future__ import annotations

from typing import Any

from anvil_uplink_cli.errors import ConfigError


def list_table_names() -> list[str]:
    """Sorted list of public Data Table names exposed on `app_tables`.

    Note: anvil-uplink's `app_tables` is a lazy proxy. `dir()` only shows
    attributes that have already been resolved plus internal bookkeeping
    (e.g. a `cache` dict). Relying on this for a full table listing is
    unreliable — callers should treat an empty result as "enumeration
    not supported", not "no tables exist".
    """
    from anvil.tables import app_tables

    names: list[str] = []
    for n in dir(app_tables):
        if n.startswith("_"):
            continue
        val = getattr(app_tables, n, None)
        # Real Data Table objects support .search(); internal attrs like the
        # proxy's `cache` dict do not.
        if callable(getattr(val, "search", None)):
            names.append(n)
    return sorted(names)


def resolve_table(table_name: str) -> Any:
    """Return the `app_tables.<name>` object or raise ConfigError if missing."""
    from anvil.tables import app_tables

    tbl = getattr(app_tables, table_name, None)
    if tbl is None:
        raise ConfigError(f"no such Data Table: {table_name!r}")
    return tbl
