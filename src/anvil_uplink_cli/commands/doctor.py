"""`anvil-bridge doctor` — connectivity + permissions check. Implemented in Checkpoint 3."""
from __future__ import annotations

import typer


def run(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    typer.echo("doctor: not yet implemented (Checkpoint 3)", err=True)
    raise typer.Exit(code=2)
