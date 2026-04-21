"""CLI smoke tests — each command's `run()` wires through Typer and its own validators.

These do NOT touch the network. Where a command would connect, we monkey-patch
`uplink` to a no-op context manager and the relevant anvil.* calls to stubs.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from anvil_uplink_cli.cli import app


@contextmanager
def _fake_uplink(*_a, **_kw):
    yield


def _write_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Create a minimal config + matching env var so resolve_key succeeds."""
    cfg_dir = tmp_path / "anvil-bridge"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text(
        "[profiles.test]\n"
        'url = "wss://anvil.works/uplink"\n'
        'key_ref = "env:TEST_UPLINK_KEY"\n'
        "default = true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("TEST_UPLINK_KEY", "fake-key-value")


def _write_impersonate_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    impersonate_callable: str | None = None,
    with_secret: bool = True,
) -> None:
    """Config + env vars for a profile that supports --as-user."""
    cfg_dir = tmp_path / "anvil-bridge"
    cfg_dir.mkdir()
    lines = [
        "[profiles.test]",
        'url = "wss://anvil.works/uplink"',
        'key_ref = "env:TEST_UPLINK_KEY"',
        "default = true",
    ]
    if with_secret:
        lines.append('impersonate_secret_ref = "env:TEST_SHARED_SECRET"')
    if impersonate_callable is not None:
        lines.append(f'impersonate_callable = "{impersonate_callable}"')
    (cfg_dir / "config.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("TEST_UPLINK_KEY", "fake-key-value")
    if with_secret:
        monkeypatch.setenv("TEST_SHARED_SECRET", "shared-123")


def test_call_happy_path(tmp_path, monkeypatch):
    _write_profile(tmp_path, monkeypatch)

    captured = {}

    def fake_call(fn_name, *args, **kwargs):
        captured["fn"] = fn_name
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"echo": list(args), "kw": kwargs}

    import anvil.server

    monkeypatch.setattr(anvil.server, "call", fake_call)
    monkeypatch.setattr(
        "anvil_uplink_cli.commands.call.uplink", _fake_uplink
    )

    result = CliRunner().invoke(
        app, ["call", "my_fn", "42", "hello", "--kwarg", 'flag=true', "--json"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {"echo": [42, "hello"], "kw": {"flag": True}}
    assert captured["fn"] == "my_fn"


def test_tables_json_output(tmp_path, monkeypatch):
    _write_profile(tmp_path, monkeypatch)

    class FakeTbl:
        def __init__(self, cols):
            self._cols = cols

        def list_columns(self):
            return self._cols

        def search(self, **_kw):  # list_table_names filters by presence of .search()
            return []

    class FakeAppTables:
        _private = "ignored"
        cache = {"internal": "not-a-table"}  # matches the anvil-uplink proxy quirk
        projects = FakeTbl([{"name": "title", "type": "string"}])
        people = FakeTbl([{"name": "email", "type": "string"}])

    import types
    fake_tables_mod = types.SimpleNamespace(app_tables=FakeAppTables())

    monkeypatch.setitem(
        __import__("sys").modules, "anvil.tables", fake_tables_mod
    )
    monkeypatch.setattr(
        "anvil_uplink_cli.commands.tables.uplink", _fake_uplink
    )

    result = CliRunner().invoke(app, ["tables", "--json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert set(data.keys()) == {"projects", "people"}
    assert data["projects"] == [{"name": "title", "type": "string"}]


def test_row_not_found(tmp_path, monkeypatch):
    _write_profile(tmp_path, monkeypatch)

    class FakeTbl:
        def get_by_id(self, _id):
            return None

    import types
    fake_tables_mod = types.SimpleNamespace(
        app_tables=types.SimpleNamespace(widgets=FakeTbl())
    )
    monkeypatch.setitem(
        __import__("sys").modules, "anvil.tables", fake_tables_mod
    )
    monkeypatch.setattr(
        "anvil_uplink_cli.commands.row.uplink", _fake_uplink
    )

    result = CliRunner().invoke(app, ["row", "widgets", "missing-id"])
    assert result.exit_code == 41  # EXIT_CONFIG — raised as ConfigError
    assert "not found" in result.stdout + result.stderr


def test_query_filter_and_limit(tmp_path, monkeypatch):
    _write_profile(tmp_path, monkeypatch)

    captured_kwargs = {}

    class FakeTbl:
        def search(self, **kwargs):
            captured_kwargs.update(kwargs)
            return [
                {"_id": "1", "name": "alpha", "priority": 1},
                {"_id": "2", "name": "beta", "priority": 2},
                {"_id": "3", "name": "gamma", "priority": 3},
            ]

    import types
    fake_tables_mod = types.SimpleNamespace(
        app_tables=types.SimpleNamespace(items=FakeTbl())
    )
    monkeypatch.setitem(
        __import__("sys").modules, "anvil.tables", fake_tables_mod
    )
    monkeypatch.setattr(
        "anvil_uplink_cli.commands.query.uplink", _fake_uplink
    )

    result = CliRunner().invoke(
        app,
        ["query", "items", "--filter", "priority=2", "--limit", "2", "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured_kwargs == {"priority": 2}
    rows = json.loads(result.stdout)
    assert len(rows) == 2  # limit respected


def test_query_wide_table_uses_vertical_fallback(tmp_path, monkeypatch):
    """Wide tables (>8 cols) must not render as a one-char-per-column smear."""
    _write_profile(tmp_path, monkeypatch)

    wide_row = {f"col_{i:02d}": f"v{i}" for i in range(20)}

    class FakeTbl:
        def search(self, **_kw):
            return [wide_row]

    import types
    fake_tables_mod = types.SimpleNamespace(
        app_tables=types.SimpleNamespace(wide=FakeTbl())
    )
    monkeypatch.setitem(
        __import__("sys").modules, "anvil.tables", fake_tables_mod
    )
    monkeypatch.setattr(
        "anvil_uplink_cli.commands.query.uplink", _fake_uplink
    )

    result = CliRunner().invoke(app, ["query", "wide"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "row 1" in result.stdout
    assert "--columns" in result.stdout  # hint is shown
    assert "col_00" in result.stdout and "col_19" in result.stdout


def test_query_columns_flag_narrows_output(tmp_path, monkeypatch):
    _write_profile(tmp_path, monkeypatch)

    class FakeTbl:
        def search(self, **_kw):
            return [
                {"_id": "1", "a": "A", "b": "B", "c": "C", "d": "D"},
            ]

    import types
    fake_tables_mod = types.SimpleNamespace(
        app_tables=types.SimpleNamespace(items=FakeTbl())
    )
    monkeypatch.setitem(
        __import__("sys").modules, "anvil.tables", fake_tables_mod
    )
    monkeypatch.setattr(
        "anvil_uplink_cli.commands.query.uplink", _fake_uplink
    )

    result = CliRunner().invoke(
        app, ["query", "items", "--columns", "a,c", "--json"]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    # --json ignores --columns (columns only affects pretty output)
    rows = json.loads(result.stdout)
    assert rows == [{"_id": "1", "a": "A", "b": "B", "c": "C", "d": "D"}]


def test_run_executes_script(tmp_path, monkeypatch):
    _write_profile(tmp_path, monkeypatch)

    script = tmp_path / "hello.py"
    script.write_text(
        "import sys\nprint('ran', sys.argv[1])\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        "anvil_uplink_cli.commands.run.uplink", _fake_uplink
    )

    result = CliRunner().invoke(app, ["run", str(script), "world"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "ran world" in result.stdout


def test_run_propagates_systemexit(tmp_path, monkeypatch):
    """H13: script's sys.exit(N) must propagate as the CLI's exit code."""
    _write_profile(tmp_path, monkeypatch)

    script = tmp_path / "bail.py"
    script.write_text("import sys\nsys.exit(5)\n", encoding="utf-8")

    monkeypatch.setattr(
        "anvil_uplink_cli.commands.run.uplink", _fake_uplink
    )

    result = CliRunner().invoke(app, ["run", str(script)])
    assert result.exit_code == 5, result.stdout + result.stderr


def test_call_as_user_happy_path(tmp_path, monkeypatch):
    _write_impersonate_profile(tmp_path, monkeypatch)

    captured = {}

    def fake_call(fn_name, *args, **kwargs):
        captured["fn"] = fn_name
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"ok": True}

    import anvil.server

    monkeypatch.setattr(anvil.server, "call", fake_call)
    monkeypatch.setattr("anvil_uplink_cli.commands.call.uplink", _fake_uplink)

    result = CliRunner().invoke(
        app,
        [
            "call",
            "my_fn",
            "--as-user",
            "svc@example.internal",
            "42",
            "--kwarg",
            "flag=true",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["fn"] == "_uplink_run_as"
    # (secret, email, target_fn, args_list, kwargs_dict)
    assert captured["args"] == (
        "shared-123",
        "svc@example.internal",
        "my_fn",
        [42],
        {"flag": True},
    )
    assert captured["kwargs"] == {}
    assert json.loads(result.stdout) == {"ok": True}


def test_call_as_user_without_impersonate_secret_ref_exits_42(tmp_path, monkeypatch):
    _write_impersonate_profile(tmp_path, monkeypatch, with_secret=False)

    def fake_call(*_a, **_kw):
        raise AssertionError("must not reach anvil.server.call without a secret_ref")

    import anvil.server

    monkeypatch.setattr(anvil.server, "call", fake_call)
    monkeypatch.setattr("anvil_uplink_cli.commands.call.uplink", _fake_uplink)

    result = CliRunner().invoke(
        app, ["call", "my_fn", "--as-user", "svc@example.internal"]
    )
    assert result.exit_code == 42, result.stdout + result.stderr
    assert "impersonation error" in (result.stdout + result.stderr)
    assert "impersonate_secret_ref" in (result.stdout + result.stderr)


def test_call_as_user_propagates_server_permission_error(tmp_path, monkeypatch):
    _write_impersonate_profile(tmp_path, monkeypatch)

    # Simulate the server-side hardened helper rejecting a bad secret.
    # map_exception routes AnvilWrappedError -> EXIT_SERVER_RAISED (30).
    import anvil.server

    class _FakeWrapped(Exception):
        type = "PermissionError"

    # Register the fake as AnvilWrappedError so errors.map_exception catches it.
    monkeypatch.setattr(
        "anvil_uplink_cli.errors.AnvilWrappedError", _FakeWrapped, raising=False
    )

    def fake_call(*_a, **_kw):
        raise _FakeWrapped("_uplink_run_as: invalid shared secret")

    monkeypatch.setattr(anvil.server, "call", fake_call)
    monkeypatch.setattr("anvil_uplink_cli.commands.call.uplink", _fake_uplink)

    result = CliRunner().invoke(
        app, ["call", "my_fn", "--as-user", "svc@example.internal"]
    )
    assert result.exit_code == 30, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "server raised PermissionError" in combined
    assert "invalid shared secret" in combined


def test_call_as_user_uses_custom_dispatcher_name(tmp_path, monkeypatch):
    _write_impersonate_profile(
        tmp_path, monkeypatch, impersonate_callable="my_shim"
    )

    captured = {}

    def fake_call(fn_name, *args, **kwargs):
        captured["fn"] = fn_name
        return "ok"

    import anvil.server

    monkeypatch.setattr(anvil.server, "call", fake_call)
    monkeypatch.setattr("anvil_uplink_cli.commands.call.uplink", _fake_uplink)

    result = CliRunner().invoke(
        app, ["call", "my_fn", "--as-user", "svc@example.internal", "--json"]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["fn"] == "my_shim"


def test_run_tolerates_utf8_bom(tmp_path, monkeypatch):
    """PowerShell's `Out-File -Encoding utf8` prepends U+FEFF; run must handle it."""
    _write_profile(tmp_path, monkeypatch)

    script = tmp_path / "bom.py"
    # utf-8-sig encoding writes the BOM prefix that PowerShell writes on Windows.
    script.write_text("print('no bom no problem')\n", encoding="utf-8-sig")

    monkeypatch.setattr(
        "anvil_uplink_cli.commands.run.uplink", _fake_uplink
    )

    result = CliRunner().invoke(app, ["run", str(script)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "no bom no problem" in result.stdout
