"""`anvil-bridge row <table> <id>` — fetch one row. Implemented in Checkpoint 4."""
from __future__ import annotations

import typer


def run(
    table: str = typer.Argument(..., help="Data Table name."),
    row_id: str = typer.Argument(..., help="Row id returned by get_id()."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    typer.echo("row: not yet implemented (Checkpoint 4)", err=True)
    raise typer.Exit(code=2)
