"""`anvil-bridge call <fn> [args]` — invoke a @anvil.server.callable and print the result."""
from __future__ import annotations

import anvil.server
import typer
from rich.console import Console

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.args import parse as parse_args
from anvil_uplink_cli.config import (
    DEFAULT_IMPERSONATE_CALLABLE,
    load_config,
    resolve_impersonate_secret,
)
from anvil_uplink_cli.connection import uplink
from anvil_uplink_cli.serialize import to_json, to_jsonable

_console = Console()


def run(
    fn: str = typer.Argument(..., help="Server function name."),
    positionals: list[str] = typer.Argument(
        None, help="Positional arguments (bare tokens are auto-coerced)."
    ),
    json_args: list[str] = typer.Option(
        None, "--arg", "-a", help="Positional arg parsed as JSON. Repeatable."
    ),
    json_kwargs: list[str] = typer.Option(
        None, "--kwarg", "-k", help="Keyword arg as name=<json>. Repeatable."
    ),
    from_stdin: bool = typer.Option(
        False, "--stdin", help="Read one JSON blob from stdin as the sole positional."
    ),
    profile_name: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output."),
    as_user: str | None = typer.Option(
        None,
        "--as-user",
        "-u",
        help=(
            "Impersonate this user (email) via the app's _uplink_run_as helper. "
            "Requires impersonate_secret_ref in the profile. "
            "See docs/impersonation.md."
        ),
    ),
) -> None:
    run_or_exit(
        lambda: _call(
            fn=fn,
            positionals=positionals,
            json_args=json_args,
            json_kwargs=json_kwargs,
            from_stdin=from_stdin,
            profile_name=profile_name,
            json_out=json_out,
            as_user=as_user,
        )
    )


def _call(
    *,
    fn: str,
    positionals: list[str] | None,
    json_args: list[str] | None,
    json_kwargs: list[str] | None,
    from_stdin: bool,
    profile_name: str | None,
    json_out: bool,
    as_user: str | None = None,
) -> None:
    parsed = parse_args(positionals, json_args, json_kwargs, use_stdin=from_stdin)
    cfg = load_config()
    prof = cfg.get(profile_name)
    # Resolve the shared secret BEFORE connecting so missing config fails fast.
    impersonate_secret = resolve_impersonate_secret(prof) if as_user else None
    with uplink(prof):
        if as_user:
            dispatcher = prof.impersonate_callable or DEFAULT_IMPERSONATE_CALLABLE
            result = anvil.server.call(
                dispatcher,
                impersonate_secret,
                as_user,
                fn,
                list(parsed.args),
                parsed.kwargs,
            )
        else:
            result = anvil.server.call(fn, *parsed.args, **parsed.kwargs)
        # Serialize inside the connection — callable returns are usually plain,
        # but may contain Row/Media LiveObjects that need the socket open.
        jsonable = to_jsonable(result)

    if json_out:
        typer.echo(to_json(jsonable, indent=2))
        return

    if jsonable is None or isinstance(jsonable, (bool, int, float, str)):
        _console.print(jsonable)
        return
    _console.print_json(to_json(jsonable))
