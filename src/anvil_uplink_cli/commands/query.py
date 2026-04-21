"""`anvil-bridge query <table> [--filter k=v] [--limit N]` — Data Table search.

Filter values use the same auto-coercion as `call`'s bare positional tokens:
    name=42    -> {"name": 42}
    active=true -> {"active": True}
    status=open -> {"status": "open"}

For explicit JSON typing, use `--filter-json name=<json>` — e.g.
    --filter-json tags='["urgent","review"]'

Server Uplink required (Client Uplink raises PermissionDenied).
"""
from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.args import coerce_bare
from anvil_uplink_cli.commands._tables import resolve_table
from anvil_uplink_cli.config import load_config
from anvil_uplink_cli.connection import uplink
from anvil_uplink_cli.serialize import to_json, to_jsonable

_console = Console()


def run(
    table: str = typer.Argument(..., help="Data Table name."),
    filters: list[str] = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter in name=value form (value auto-coerced). Repeatable.",
    ),
    filters_json: list[str] = typer.Option(
        None,
        "--filter-json",
        help="Filter in name=<json> form (value parsed as JSON). Repeatable.",
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-n", help="Maximum rows to return."
    ),
    columns: str | None = typer.Option(
        None,
        "--columns",
        "-c",
        help="Comma-separated column allow-list (e.g. 'id,name,status'). Default: all.",
    ),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output."),
) -> None:
    run_or_exit(
        lambda: _query(table, filters, filters_json, limit, columns, profile, json_out)
    )


def _split_filter(raw: str, flag: str) -> tuple[str, str]:
    if "=" not in raw:
        raise ValueError(f"{flag} expects name=value, got: {raw!r}")
    name, _, value = raw.partition("=")
    name = name.strip()
    if not name.isidentifier():
        raise ValueError(f"{flag} name is not a valid identifier: {name!r}")
    return name, value


def _parse_filters(
    bare: list[str] | None, as_json: list[str] | None
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw in bare or []:
        name, value = _split_filter(raw, "--filter")
        out[name] = coerce_bare(value)
    for raw in as_json or []:
        name, value = _split_filter(raw, "--filter-json")
        try:
            out[name] = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"--filter-json {name}: invalid JSON: {e.msg} (at pos {e.pos})"
            ) from e
    return out


def _collect_rows(tbl: Any, kwargs: dict[str, Any], limit: int | None) -> list[Any]:
    iterator = tbl.search(**kwargs)
    if limit is None:
        return list(iterator)
    out: list[Any] = []
    for i, row in enumerate(iterator):
        if i >= limit:
            break
        out.append(row)
    return out


# When the user doesn't pick columns, switch from horizontal to vertical
# layout past this many keys — beyond ~8 cols, Rich's fold degenerates into
# single-character columns in a normal terminal.
_WIDE_TABLE_THRESHOLD = 8


def _query(
    table_name: str,
    filters: list[str] | None,
    filters_json: list[str] | None,
    limit: int | None,
    columns: str | None,
    profile_name: str | None,
    json_out: bool,
) -> None:
    kwargs = _parse_filters(filters, filters_json)
    cfg = load_config()
    prof = cfg.get(profile_name)
    with uplink(prof):
        tbl = resolve_table(table_name)
        rows = _collect_rows(tbl, kwargs, limit)
        # Serialize while the connection is still open — Row is a LiveObject;
        # link columns and lazy Media can trigger additional round-trips.
        jsonable = [to_jsonable(r) for r in rows]

    if json_out:
        typer.echo(to_json(jsonable, indent=2))
        return

    if not jsonable:
        _console.print(f"[dim]no rows matched in {table_name}[/]")
        return

    # Pretty: rich table with union of keys as columns (dicts only)
    if not all(isinstance(r, dict) for r in jsonable):
        _console.print_json(to_json(jsonable))
        return

    all_keys = list(dict.fromkeys(k for r in jsonable for k in r.keys()))
    picked = _pick_columns(all_keys, columns)
    if not picked:
        _console.print(
            f"[yellow]note[/]: --columns matched nothing in {table_name}. "
            f"Available: {', '.join(all_keys)}"
        )
        return

    count = len(jsonable)
    suffix = "" if count == 1 else "s"
    title = f"{table_name} [dim]({count} row{suffix})[/]"

    user_picked = columns is not None
    if not user_picked and len(picked) > _WIDE_TABLE_THRESHOLD:
        _render_vertical(title, picked, jsonable, total_keys=len(all_keys))
        return

    _render_horizontal(title, picked, jsonable)


def _pick_columns(all_keys: list[str], spec: str | None) -> list[str]:
    if spec is None:
        return all_keys
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    available = set(all_keys)
    return [k for k in wanted if k in available]


def _render_horizontal(title: str, keys: list[str], rows: list[dict[str, Any]]) -> None:
    t = Table(title=title, show_header=True, header_style="bold")
    for k in keys:
        t.add_column(k, overflow="fold")
    for r in rows:
        t.add_row(*[_cell(r.get(k)) for k in keys])
    _console.print(t)


def _render_vertical(
    title: str, keys: list[str], rows: list[dict[str, Any]], total_keys: int
) -> None:
    _console.print(title)
    _console.print(
        f"[dim]wide table ({total_keys} columns) — showing as records. "
        f"Use [bold]--columns a,b,c[/bold] to pick or [bold]--json[/bold] for the full payload.[/dim]"
    )
    key_width = max(len(k) for k in keys)
    for i, r in enumerate(rows, start=1):
        _console.print(f"[bold cyan]— row {i} —[/]")
        for k in keys:
            _console.print(f"  [bold]{k.ljust(key_width)}[/]  {_cell(r.get(k))}")


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    return json.dumps(v, ensure_ascii=False, default=str)
