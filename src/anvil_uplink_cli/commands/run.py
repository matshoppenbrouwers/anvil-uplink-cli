"""`anvil-bridge run <script.py>` — execute a local Python file with the uplink connected.

The script runs in its own globals namespace with `__name__ == "__main__"`
so `if __name__ == "__main__":` blocks fire correctly. `anvil`, `anvil.server`,
and `app_tables` (when accessible) are pre-imported into the namespace for
convenience — scripts do not need to manage the connection themselves.

SystemExit is propagated so a script's `sys.exit(N)` gives the CLI exit code N.
Any other exception surfaces through run_or_exit's exception mapper.
"""
from __future__ import annotations

import builtins
import sys
from pathlib import Path
from typing import Any

import typer

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.config import load_config
from anvil_uplink_cli.connection import uplink
from anvil_uplink_cli.errors import ConfigError


def run(
    script: str = typer.Argument(..., help="Path to a local Python script."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    args: list[str] = typer.Argument(
        None,
        help="Arguments passed to the script as sys.argv[1:].",
    ),
) -> None:
    run_or_exit(lambda: _run(script, profile, args or []))


def _build_namespace(script_path: Path) -> dict[str, Any]:
    import anvil
    import anvil.server

    ns: dict[str, Any] = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__builtins__": builtins.__dict__,
        "anvil": anvil,
        "server": anvil.server,
    }
    try:
        from anvil.tables import app_tables

        ns["app_tables"] = app_tables
    except Exception:
        pass
    return ns


def _run(script: str, profile_name: str | None, script_args: list[str]) -> None:
    path = Path(script).expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"script not found: {path}")
    if not path.is_file():
        raise ConfigError(f"not a file: {path}")

    compiled = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    cfg = load_config()
    prof = cfg.get(profile_name)

    original_argv = sys.argv
    sys.argv = [str(path), *script_args]
    try:
        with uplink(prof):
            exec(compiled, _build_namespace(path))
    finally:
        sys.argv = original_argv
