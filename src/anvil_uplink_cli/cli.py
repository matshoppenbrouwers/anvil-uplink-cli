"""Typer application entry point. Wires subcommands."""
from __future__ import annotations

import typer

from anvil_uplink_cli import __version__
from anvil_uplink_cli.commands import (
    call as call_cmd,
)
from anvil_uplink_cli.commands import (
    doctor as doctor_cmd,
)
from anvil_uplink_cli.commands import (
    init as init_cmd,
)
from anvil_uplink_cli.commands import (
    query as query_cmd,
)
from anvil_uplink_cli.commands import (
    repl as repl_cmd,
)
from anvil_uplink_cli.commands import (
    row as row_cmd,
)
from anvil_uplink_cli.commands import (
    run as run_cmd,
)
from anvil_uplink_cli.commands import (
    tables as tables_cmd,
)

app = typer.Typer(
    name="anvil-bridge",
    help="Terminal bridge to Anvil apps via the Server Uplink.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"anvil-bridge {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Entry point; global options live here."""


app.command("init", help="Create or update a profile (interactive).")(init_cmd.run)
app.command("doctor", help="Verify connectivity and list accessible tables.")(doctor_cmd.run)
app.command("call", help="Invoke @anvil.server.callable and print the result.")(call_cmd.run)
app.command("query", help="Search a Data Table with filters.")(query_cmd.run)
app.command("tables", help="List Data Tables and their column schemas.")(tables_cmd.run)
app.command("row", help="Fetch a single row by id.")(row_cmd.run)
app.command("run", help="Run a local Python script with the uplink pre-connected.")(run_cmd.run)
app.command("repl", help="Interactive Python shell with the uplink live.")(repl_cmd.run)


if __name__ == "__main__":
    app()
