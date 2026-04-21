"""Convert Anvil return values to JSON-safe Python values.

Handles: anvil.tables.Row, anvil.Media/BlobMedia/LazyMedia, datetime/date/time,
portable classes (anything with __serialize__), plus normal dict/list/tuple/set
recursion. Falls through for primitives.

We duck-type rather than import anvil.tables.Row directly because the exact
class varies between uplink and in-app contexts, and some types proxy as
dict-like LiveObjects.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Any

# Duck-type probes (avoid hard imports that could fail in some environments)
_ROW_MARKER = "get_id"  # anvil.tables.Row.get_id()
_MEDIA_ATTRS = ("content_type", "length")


def _is_row(obj: Any) -> bool:
    return (
        hasattr(obj, _ROW_MARKER)
        and callable(getattr(obj, _ROW_MARKER, None))
        and hasattr(obj, "__iter__")  # dict-like iteration of columns
        and hasattr(obj, "__getitem__")
    )


def _is_media(obj: Any) -> bool:
    return all(hasattr(obj, a) for a in _MEDIA_ATTRS)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Serialize an anvil.tables.Row.

    anvil-uplink's Row iteration is not consistent across versions: some yield
    column names (keys only), others yield `(key, value)` pairs dict.items()-style.
    Handle both shapes without a try/except-on-indexing dance.
    """
    out: dict[str, Any] = {"_id": row.get_id()}
    try:
        items = list(row)
    except TypeError:
        return out
    for item in items:
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[0], str)
        ):
            key, value = item
            try:
                out[key] = to_jsonable(value)
            except Exception as e:  # one bad column shouldn't poison the row
                out[key] = {"_unserializable": type(e).__name__, "detail": str(e)}
            continue
        if not isinstance(item, str):
            # Unknown iteration shape; skip with a breadcrumb rather than crash.
            out[repr(item)] = {"_unserializable": "BadIterationShape"}
            continue
        key = item
        try:
            out[key] = to_jsonable(row[key])
        except Exception as e:
            out[key] = {"_unserializable": type(e).__name__, "detail": str(e)}
    return out


def _media_to_dict(media: Any) -> dict[str, Any]:
    return {
        "_type": "Media",
        "content_type": getattr(media, "content_type", None),
        "length": getattr(media, "length", None),
        "name": getattr(media, "name", None),
        "url": getattr(media, "url", None),
    }


def to_jsonable(value: Any) -> Any:
    """Recursively convert `value` to JSON-serializable primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return {"_type": "bytes", "length": len(value)}
    # Row / Media detection uses duck-typing; order matters (Row is more specific)
    if _is_row(value):
        return _row_to_dict(value)
    if _is_media(value):
        return _media_to_dict(value)
    if hasattr(value, "__serialize__") and callable(value.__serialize__):
        try:
            data = value.__serialize__({})
            return {
                "_portable_class": type(value).__name__,
                "data": to_jsonable(data),
            }
        except Exception as e:
            return {"_portable_class": type(value).__name__, "_error": str(e)}
    # Last resort: stringify
    return {"_repr": repr(value), "_type": type(value).__name__}


def to_json(value: Any, *, indent: int | None = None) -> str:
    """Shortcut: jsonable → json.dumps. Always safe; never raises on weird inputs."""
    return json.dumps(to_jsonable(value), indent=indent, ensure_ascii=False, default=str)
