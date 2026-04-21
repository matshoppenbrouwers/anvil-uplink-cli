"""Shared error-handling wrapper for command functions.

Every command's `run()` does roughly:
    1. resolve profile
    2. connect
    3. do work
    4. disconnect
    5. print
Steps 1+2 can raise AuthError/ConfigError; step 3 can raise any anvil.server
exception. This module centralizes the exception → exit code mapping so each
command stays focused on its actual work.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TypeVar

import click
import typer

from anvil_uplink_cli.errors import (
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_IMPERSONATION,
    EXIT_USAGE,
    AuthError,
    ConfigError,
    ImpersonationError,
    map_exception,
)

T = TypeVar("T")


def run_or_exit(work: Callable[[], T]) -> T:
    """Run `work()` and translate any exception into a clean CLI error + exit.

    On success: returns the work function's return value.
    On known error: prints to stderr, exits with the mapped code.
    On unknown error: prints a generic unexpected message, exits 1.
    """
    try:
        return work()
    except ConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=EXIT_CONFIG) from e
    except AuthError as e:
        typer.echo(f"auth error: {e}", err=True)
        raise typer.Exit(code=EXIT_AUTH) from e
    except ImpersonationError as e:
        typer.echo(f"impersonation error: {e}", err=True)
        raise typer.Exit(code=EXIT_IMPERSONATION) from e
    except ValueError as e:
        # Arg / filter parsing raises ValueError; treat as usage error.
        typer.echo(f"usage error: {e}", err=True)
        raise typer.Exit(code=EXIT_USAGE) from e
    except typer.Exit:
        raise
    except click.UsageError:
        # Let Typer/Click's top-level handler render + exit 2.
        raise
    except KeyboardInterrupt:
        typer.echo("interrupted", err=True)
        sys.exit(130)
    except Exception as e:
        mapped = map_exception(e)
        typer.echo(f"error: {mapped.message}", err=True)
        raise typer.Exit(code=mapped.exit_code) from e
