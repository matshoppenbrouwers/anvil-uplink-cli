"""`anvil-bridge repl` — interactive Python shell. Implemented in Checkpoint 5."""
from __future__ import annotations

import typer


def run(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
) -> None:
    typer.echo("repl: not yet implemented (Checkpoint 5)", err=True)
    raise typer.Exit(code=2)
