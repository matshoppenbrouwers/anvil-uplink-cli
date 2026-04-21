"""`anvil-bridge doctor` — verify connectivity and enumerate accessible tables.

Reports:
- Which profile is used
- Uplink URL
- Whether connect/disconnect succeeds
- Whether Data Tables are accessible (Server Uplink) or restricted (Client Uplink)
- Names of accessible tables
"""
from __future__ import annotations

import typer
from rich.console import Console

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.commands._tables import list_table_names
from anvil_uplink_cli.config import load_config
from anvil_uplink_cli.connection import uplink
from anvil_uplink_cli.errors import PermissionDenied, map_exception
from anvil_uplink_cli.serialize import to_json

_console = Console()


def run(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output."),
) -> None:
    run_or_exit(lambda: _doctor(profile, json_out))


def _doctor(profile_name: str | None, json_out: bool) -> None:
    cfg = load_config()
    prof = cfg.get(profile_name)
    report: dict[str, object] = {
        "profile": prof.name,
        "url": prof.url,
        "connected": False,
        "uplink_type": "unknown",
        "tables": [],
    }
    with uplink(prof):
        report["connected"] = True
        try:
            tables = list_table_names()
            report["uplink_type"] = "server"
            report["tables"] = tables
        except Exception as e:
            if PermissionDenied is not None and isinstance(e, PermissionDenied):
                report["uplink_type"] = "client"
                report["error"] = "Client Uplink cannot enumerate Data Tables"
            else:
                mapped = map_exception(e)
                report["error"] = mapped.message
                report["uplink_type"] = "error"

    if json_out:
        typer.echo(to_json(report, indent=2))
        return

    _console.print(f"[bold]profile[/]: {report['profile']}")
    _console.print(f"[bold]url[/]:     {report['url']}")
    uplink_type = report["uplink_type"]
    if uplink_type == "error":
        _console.print("[bold]connected[/]: [yellow]partial[/] (connected, but enumeration failed)")
    else:
        _console.print("[bold]connected[/]: [green]yes[/]")
    type_color = {"server": "green", "client": "yellow", "error": "red"}.get(str(uplink_type), "dim")
    _console.print(f"[bold]uplink type[/]: [{type_color}]{uplink_type}[/]")
    tables = report["tables"]
    if isinstance(tables, list) and tables:
        _console.print(f"[bold]tables ({len(tables)})[/]:")
        for t in tables:
            _console.print(f"  • {t}")
    elif report.get("error"):
        _console.print(f"[yellow]note[/]: {report['error']}")
    else:
        _console.print("[dim]no tables accessible[/]")
