"""`anvil-bridge tables` — list Data Tables. Implemented in Checkpoint 4."""
from __future__ import annotations

import typer


def run(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    typer.echo("tables: not yet implemented (Checkpoint 4)", err=True)
    raise typer.Exit(code=2)
