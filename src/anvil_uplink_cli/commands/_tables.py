"""Shared helpers for commands that touch `anvil.tables.app_tables`.

Lazy-imports `app_tables` so the cost only lands when a command actually
needs it, and so modules that merely import a command (e.g. `cli.py`)
don't transitively pull `anvil.tables`.
"""
from __future__ import annotations

from typing import Any

from anvil_uplink_cli.errors import ConfigError


def list_table_names() -> list[str]:
    """Sorted list of public attributes on `app_tables` (i.e. table names)."""
    from anvil.tables import app_tables

    return sorted(n for n in dir(app_tables) if not n.startswith("_"))


def resolve_table(table_name: str) -> Any:
    """Return the `app_tables.<name>` object or raise ConfigError if missing."""
    from anvil.tables import app_tables

    tbl = getattr(app_tables, table_name, None)
    if tbl is None:
        raise ConfigError(f"no such Data Table: {table_name!r}")
    return tbl
