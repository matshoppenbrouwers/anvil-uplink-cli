"""Sanity tests for the scaffold — imports resolve, CLI loads, --help works."""
from __future__ import annotations

from typer.testing import CliRunner

from anvil_uplink_cli import __version__
from anvil_uplink_cli.cli import app


def test_version_is_set() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_lists_all_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("init", "doctor", "call", "query", "tables", "row", "run", "repl"):
        assert cmd in result.stdout


def test_cli_version_flag() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
