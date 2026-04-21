"""Tests for serialize.to_jsonable / to_json."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timezone

import pytest

from anvil_uplink_cli.serialize import to_json, to_jsonable


# Fake Row / Media with the minimum duck-type surface
class FakeRow:
    def __init__(self, row_id: str, data: dict) -> None:
        self._id = row_id
        self._data = data

    def get_id(self) -> str:
        return self._id

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, k):
        return self._data[k]


class FakeMedia:
    def __init__(self, name: str, content_type: str, length: int) -> None:
        self.name = name
        self.content_type = content_type
        self.length = length
        self.url = f"https://media.example/{name}"


class _Portable:
    def __init__(self, first: str, last: str) -> None:
        self.first, self.last = first, last

    def __serialize__(self, global_data: dict) -> list[str]:
        return [self.first, self.last]


@pytest.mark.parametrize(
    "v",
    [None, True, False, 0, 1, -1, 1.5, "hi", ""],
)
def test_primitives_pass_through(v: object) -> None:
    assert to_jsonable(v) == v


def test_datetime_iso() -> None:
    dt = datetime(2026, 4, 20, 13, 0, tzinfo=timezone.utc)
    assert to_jsonable(dt) == "2026-04-20T13:00:00+00:00"
    assert to_jsonable(date(2026, 1, 1)) == "2026-01-01"
    assert to_jsonable(time(9, 30)) == "09:30:00"


def test_nested_dict_and_list() -> None:
    assert to_jsonable({"a": [1, 2, {"b": True}]}) == {"a": [1, 2, {"b": True}]}


def test_tuple_and_set_become_list() -> None:
    assert to_jsonable((1, 2, 3)) == [1, 2, 3]
    assert sorted(to_jsonable({1, 2, 3})) == [1, 2, 3]


def test_bytes_is_stubbed() -> None:
    out = to_jsonable(b"hello")
    assert out == {"_type": "bytes", "length": 5}


def test_row() -> None:
    row = FakeRow("abc-123", {"name": "Alice", "age": 30})
    out = to_jsonable(row)
    assert out == {"_id": "abc-123", "name": "Alice", "age": 30}


class FakeItemsRow:
    """Mirrors anvil-uplink's observed Row: iteration yields (key, value) pairs."""

    def __init__(self, row_id: str, data: dict) -> None:
        self._id = row_id
        self._data = data

    def get_id(self) -> str:
        return self._id

    def __iter__(self):
        return iter(list(self._data.items()))

    def __getitem__(self, k):
        return self._data[k]


def test_row_iter_yields_items_pairs() -> None:
    # Regression: observed against lat-profit's bamboo_pay_history, where
    # `list(row)` returns [[k, v], ...] instead of [k, ...]. Old serializer
    # did `out[k] = ...` with k as a list → TypeError: unhashable type: 'list'.
    row = FakeItemsRow("xyz-9", {"email": "a@b.c", "active": True})
    out = to_jsonable(row)
    assert out == {"_id": "xyz-9", "email": "a@b.c", "active": True}


def test_row_with_nested_row() -> None:
    parent = FakeRow("parent-1", {"title": "Top"})
    child = FakeRow("child-1", {"parent": parent, "n": 1})
    out = to_jsonable(child)
    assert out["_id"] == "child-1"
    assert out["n"] == 1
    assert out["parent"]["_id"] == "parent-1"


def test_media() -> None:
    m = FakeMedia("a.png", "image/png", 1024)
    out = to_jsonable(m)
    assert out["_type"] == "Media"
    assert out["content_type"] == "image/png"
    assert out["length"] == 1024
    assert out["name"] == "a.png"
    assert out["url"] == "https://media.example/a.png"


def test_portable_class() -> None:
    p = _Portable("Ada", "Lovelace")
    out = to_jsonable(p)
    assert out == {"_portable_class": "_Portable", "data": ["Ada", "Lovelace"]}


def test_unknown_object_gets_repr_stub() -> None:
    class X:
        def __repr__(self) -> str:
            return "<X-obj>"

    out = to_jsonable(X())
    assert out["_type"] == "X"
    assert out["_repr"] == "<X-obj>"


def test_to_json_roundtrip() -> None:
    payload = {"when": datetime(2026, 4, 20, tzinfo=timezone.utc), "n": 3}
    s = to_json(payload)
    parsed = json.loads(s)
    assert parsed == {"when": "2026-04-20T00:00:00+00:00", "n": 3}


def test_to_json_indent() -> None:
    s = to_json({"a": 1}, indent=2)
    assert "\n" in s
    assert '"a": 1' in s


def test_bad_column_does_not_crash_row() -> None:
    class BadRow(FakeRow):
        def __getitem__(self, k):
            if k == "poison":
                raise RuntimeError("boom")
            return super().__getitem__(k)

    row = BadRow("r1", {"ok": 1, "poison": None})
    out = to_jsonable(row)
    assert out["_id"] == "r1"
    assert out["ok"] == 1
    assert out["poison"]["_unserializable"] == "RuntimeError"
