"""`anvil-bridge run <script.py>` — run local Python with uplink live. Implemented in Checkpoint 5."""
from __future__ import annotations

import typer


def run(
    script: str = typer.Argument(..., help="Path to a local Python script."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
) -> None:
    typer.echo("run: not yet implemented (Checkpoint 5)", err=True)
    raise typer.Exit(code=2)
