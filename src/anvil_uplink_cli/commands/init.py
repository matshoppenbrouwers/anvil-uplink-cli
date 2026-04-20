"""`anvil-bridge init` — interactive profile wizard. Implemented in Checkpoint 3."""
from __future__ import annotations

import typer


def run() -> None:
    typer.echo("init: not yet implemented (Checkpoint 3)", err=True)
    raise typer.Exit(code=2)
