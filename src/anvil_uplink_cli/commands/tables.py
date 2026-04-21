"""`anvil-bridge tables` — list Data Tables visible to the key + column schemas.

Server Uplink sees every table; Client Uplink raises PermissionDenied before
the iteration even begins. We let that exception bubble up to `_runner.py`,
which maps it to the right exit code and message.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.commands._tables import list_table_names
from anvil_uplink_cli.config import load_config
from anvil_uplink_cli.connection import uplink
from anvil_uplink_cli.serialize import to_json

_console = Console()


def run(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output."),
) -> None:
    run_or_exit(lambda: _tables(profile, json_out))


def _collect_schema() -> dict[str, list[dict[str, str]]]:
    from anvil.tables import app_tables

    out: dict[str, list[dict[str, str]]] = {}
    for name in list_table_names():
        tbl = getattr(app_tables, name)
        cols_fn = getattr(tbl, "list_columns", None)
        if not callable(cols_fn):
            out[name] = []
            continue
        try:
            cols = cols_fn() or []
        except Exception as e:  # one bad table shouldn't hide the rest
            out[name] = [{"_error": f"{type(e).__name__}: {e}"}]
            continue
        out[name] = [
            {
                "name": str(c.get("name", "")),
                "type": str(c.get("type", "")),
            }
            for c in cols
            if isinstance(c, dict)
        ]
    return out


def _tables(profile_name: str | None, json_out: bool) -> None:
    cfg = load_config()
    prof = cfg.get(profile_name)
    with uplink(prof):
        schema = _collect_schema()

    if json_out:
        typer.echo(to_json(schema, indent=2))
        return

    if not schema:
        _console.print(
            "[yellow]note[/]: anvil-uplink does not expose a list of Data Tables over the wire. "
            "This command relies on `dir(app_tables)`, which is unreliable. "
            "Consult your app's [bold]anvil.yaml[/bold] ([bold]db_schema[/bold] section) for table names, "
            "then use [bold]`anvil-bridge query <table>`[/bold] or [bold]`row <table> <id>`[/bold] directly."
        )
        return

    for name, cols in schema.items():
        title = f"{name}  [dim]({len(cols)} columns)[/]"
        if not cols:
            _console.print(title)
            continue
        t = Table(title=title, show_header=True, header_style="bold", expand=False)
        t.add_column("column")
        t.add_column("type")
        for c in cols:
            if "_error" in c:
                t.add_row("[red]error[/]", c["_error"])
            else:
                t.add_row(c.get("name", ""), c.get("type", ""))
        _console.print(t)
