"""`anvil-bridge query <table>` — Data Table search. Implemented in Checkpoint 4."""
from __future__ import annotations

import typer


def run(
    table: str = typer.Argument(..., help="Data Table name."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    filters: list[str] = typer.Option(None, "--filter", "-f", help="Filter in k=v form."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum rows to return."),
    json_out: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    typer.echo("query: not yet implemented (Checkpoint 4)", err=True)
    raise typer.Exit(code=2)
