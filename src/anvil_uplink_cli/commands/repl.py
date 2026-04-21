"""`anvil-bridge repl` — interactive Python shell with the uplink connected.

Drops you into code.InteractiveConsole with `anvil`, `anvil.server`, and
`app_tables` pre-imported. Connection lifecycle is wrapped in `uplink(...)`,
so Ctrl-D / SystemExit / exceptions all trigger a clean disconnect.

Known limitation: this is a plain `code` REPL, not IPython — no tab-completion
or line editing beyond what `readline` provides on the host. That's fine for
ad-hoc diagnostics; for richer shells, use `run <script.py>` instead.
"""
from __future__ import annotations

import code
from typing import Any

import typer

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.config import load_config
from anvil_uplink_cli.connection import uplink


def run(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
) -> None:
    run_or_exit(lambda: _repl(profile))


def _build_namespace() -> dict[str, Any]:
    import anvil
    import anvil.server

    ns: dict[str, Any] = {"anvil": anvil, "server": anvil.server}
    try:
        from anvil.tables import app_tables

        ns["app_tables"] = app_tables
    except Exception:
        pass
    return ns


def _repl(profile_name: str | None) -> None:
    cfg = load_config()
    prof = cfg.get(profile_name)

    # Try to enable readline for basic line editing / history; best-effort.
    try:
        import readline  # noqa: F401
    except ImportError:
        pass

    banner = (
        f"anvil-bridge repl — profile '{prof.name}' ({prof.url})\n"
        "available: anvil, server (= anvil.server), app_tables (if accessible)\n"
        "Ctrl-D to exit."
    )
    with uplink(prof):
        ns = _build_namespace()
        console = code.InteractiveConsole(locals=ns)
        try:
            console.interact(banner=banner, exitmsg="")
        except SystemExit:
            pass
