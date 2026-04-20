"""Parse CLI positional / --arg / --kwarg into Python args for anvil.server.call.

Rules
-----
Bare positional tokens are auto-coerced:
    "42"        -> int(42)
    "3.14"      -> float(3.14)
    "true"      -> True       (case-insensitive)
    "false"     -> False
    "null"      -> None
    "none"      -> None
    anything else -> str

Explicit typing via flags:
    --arg '<json>'        -> one positional arg, parsed as JSON
    --kwarg name=<json>   -> keyword arg, value parsed as JSON
    --stdin               -> read one JSON blob from stdin, use as sole positional

--arg / --kwarg win over auto-coercion: if you pass --arg, it's appended after
any bare positionals in order of appearance on the command line. The CLI layer
is responsible for preserving that order.

Typer passes --arg and --kwarg as lists already ordered. Bare positionals also
arrive as a list. We merge positionals-then-args (args first callers can adjust
if strict ordering matters, but for practical use this is fine).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass


@dataclass
class ParsedArgs:
    args: list[object]
    kwargs: dict[str, object]


_FALSY = {"false", "no", "off"}
_TRUTHY = {"true", "yes", "on"}
_NULLY = {"null", "none", "nil"}


def coerce_bare(token: str) -> object:
    """Auto-coerce a bare CLI token. Always succeeds (falls back to str)."""
    low = token.strip().lower()
    if low in _NULLY:
        return None
    if low in _TRUTHY:
        return True
    if low in _FALSY:
        return False
    try:
        return int(token)
    except ValueError:
        pass
    try:
        # don't accept "NaN"/"Infinity" as floats even though Python does —
        # they're almost never what a shell user meant
        if low in {"nan", "inf", "infinity", "-inf", "-infinity"}:
            raise ValueError
        return float(token)
    except ValueError:
        pass
    return token


def _parse_json_arg(raw: str, *, label: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"{label}: invalid JSON: {e.msg} (at pos {e.pos})") from e


def parse(
    positionals: list[str] | None,
    json_args: list[str] | None,
    json_kwargs: list[str] | None,
    use_stdin: bool = False,
) -> ParsedArgs:
    """Assemble positionals+kwargs for anvil.server.call.

    Raises ValueError on malformed --kwarg or invalid JSON.
    """
    args: list[object] = []
    kwargs: dict[str, object] = {}

    if use_stdin:
        raw = sys.stdin.read()
        if raw.strip():
            args.append(_parse_json_arg(raw, label="--stdin"))

    for tok in positionals or []:
        args.append(coerce_bare(tok))

    for raw in json_args or []:
        args.append(_parse_json_arg(raw, label="--arg"))

    for raw in json_kwargs or []:
        if "=" not in raw:
            raise ValueError(f"--kwarg expects name=value, got: {raw!r}")
        name, _, value = raw.partition("=")
        name = name.strip()
        if not name.isidentifier():
            raise ValueError(f"--kwarg name is not a valid identifier: {name!r}")
        kwargs[name] = _parse_json_arg(value, label=f"--kwarg {name}")

    return ParsedArgs(args=args, kwargs=kwargs)
