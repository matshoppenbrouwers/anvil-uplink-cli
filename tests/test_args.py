"""Tests for args.coerce_bare and args.parse."""
from __future__ import annotations

import io

import pytest

from anvil_uplink_cli.args import coerce_bare, parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("42", 42),
        ("-7", -7),
        ("0", 0),
        ("3.14", 3.14),
        ("-0.5", -0.5),
        ("true", True),
        ("True", True),
        ("FALSE", False),
        ("null", None),
        ("None", None),
        ("hello", "hello"),
        ("42abc", "42abc"),
        ("", ""),
        ("nan", "nan"),  # rejected as float on purpose
        ("inf", "inf"),
    ],
)
def test_coerce_bare(raw: str, expected: object) -> None:
    assert coerce_bare(raw) == expected


def test_parse_positionals_coerced() -> None:
    out = parse(["42", "hello", "true"], None, None)
    assert out.args == [42, "hello", True]
    assert out.kwargs == {}


def test_parse_arg_as_json() -> None:
    out = parse([], ['[1,2,3]', '{"k":"v"}'], None)
    assert out.args == [[1, 2, 3], {"k": "v"}]


def test_parse_kwargs() -> None:
    out = parse([], None, ["name=\"Alice\"", "age=30", "active=true"])
    assert out.kwargs == {"name": "Alice", "age": 30, "active": True}


def test_parse_kwargs_reject_missing_equals() -> None:
    with pytest.raises(ValueError, match="name=value"):
        parse([], None, ["bogus"])


def test_parse_kwargs_reject_bad_identifier() -> None:
    with pytest.raises(ValueError, match="valid identifier"):
        parse([], None, ["1bad=true"])


def test_parse_arg_bad_json() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        parse([], ["{not json"], None)


def test_parse_kwarg_bad_json() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        parse([], None, ["x={not json"])


def test_parse_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO('{"foo":"bar"}'))
    out = parse(None, None, None, use_stdin=True)
    assert out.args == [{"foo": "bar"}]


def test_parse_empty_stdin_yields_no_arg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    out = parse(None, None, None, use_stdin=True)
    assert out.args == []


def test_parse_combines_order() -> None:
    # Rule: positionals first (coerced), then --arg entries in order
    out = parse(["1"], ['"two"'], ["k=3"])
    assert out.args == [1, "two"]
    assert out.kwargs == {"k": 3}
