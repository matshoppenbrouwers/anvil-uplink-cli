"""`anvil-bridge call <fn> [args]` — invoke @anvil.server.callable. Implemented in Checkpoint 3."""
from __future__ import annotations

import typer


def run(
    fn: str = typer.Argument(..., help="Server function name."),
    args: list[str] = typer.Argument(None, help="Positional arguments (auto-coerced)."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    typer.echo("call: not yet implemented (Checkpoint 3)", err=True)
    raise typer.Exit(code=2)
