"""`anvil-bridge row <table> <row_id>` — fetch a single row via get_by_id.

Output uses the generic serializer, so Media/datetime/portable classes all
come through safely in both pretty and --json modes.
"""
from __future__ import annotations

import typer
from rich.console import Console

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.config import load_config
from anvil_uplink_cli.connection import uplink
from anvil_uplink_cli.errors import ConfigError
from anvil_uplink_cli.serialize import to_json, to_jsonable

_console = Console()


def run(
    table: str = typer.Argument(..., help="Data Table name."),
    row_id: str = typer.Argument(..., help="Row id returned by get_id()."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output."),
) -> None:
    run_or_exit(lambda: _row(table, row_id, profile, json_out))


def _resolve_table(table_name: str):
    from anvil.tables import app_tables

    tbl = getattr(app_tables, table_name, None)
    if tbl is None:
        raise ConfigError(f"no such Data Table: {table_name!r}")
    return tbl


def _row(table_name: str, row_id: str, profile_name: str | None, json_out: bool) -> None:
    cfg = load_config()
    prof = cfg.get(profile_name)
    with uplink(prof):
        tbl = _resolve_table(table_name)
        row = tbl.get_by_id(row_id)
        if row is None:
            raise ConfigError(f"row {row_id!r} not found in table {table_name!r}")
        # Serialize inside the connection — Row columns may trigger round-trips.
        jsonable = to_jsonable(row)

    serialized = to_json(jsonable)
    if json_out:
        typer.echo(to_json(jsonable, indent=2))
        return
    _console.print_json(serialized)
