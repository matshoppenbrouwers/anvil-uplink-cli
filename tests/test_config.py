"""Tests for config load/save/resolve_key."""
from __future__ import annotations

from pathlib import Path

import pytest

from anvil_uplink_cli.config import (
    DEFAULT_IMPERSONATE_CALLABLE,
    DEFAULT_URL,
    ENV_VAR_KEY,
    Config,
    Profile,
    SecretStr,
    load_config,
    resolve_impersonate_secret,
    resolve_key,
    resolve_secret,
    save_config,
)
from anvil_uplink_cli.errors import AuthError, ConfigError, ImpersonationError


def test_profile_from_dict_defaults() -> None:
    p = Profile.from_dict("alpha", {})
    assert p.name == "alpha"
    assert p.url == DEFAULT_URL
    assert p.key_ref == ""
    assert p.default is False


def test_config_roundtrip(tmp_path: Path) -> None:
    cfg = Config()
    cfg.set_profile(Profile(name="a", url="wss://x/uplink", key_ref="env:A_KEY", default=True))
    cfg.set_profile(Profile(name="b", key_ref="env:B_KEY"))
    p = tmp_path / "config.toml"
    save_config(cfg, p)
    loaded = load_config(p)
    assert set(loaded.profiles) == {"a", "b"}
    assert loaded.profiles["a"].url == "wss://x/uplink"
    assert loaded.profiles["a"].default is True
    assert loaded.profiles["b"].default is False


def test_config_get_default_when_exactly_one_default(tmp_path: Path) -> None:
    cfg = Config()
    cfg.set_profile(Profile(name="a", default=True))
    cfg.set_profile(Profile(name="b"))
    assert cfg.get(None).name == "a"


def test_set_profile_demotes_previous_default() -> None:
    cfg = Config()
    cfg.set_profile(Profile(name="a", default=True))
    cfg.set_profile(Profile(name="b", default=True))
    assert cfg.profiles["a"].default is False
    assert cfg.profiles["b"].default is True


def test_config_get_single_profile_without_default_flag() -> None:
    cfg = Config()
    cfg.set_profile(Profile(name="only"))
    assert cfg.get(None).name == "only"


def test_config_get_unknown_profile_raises() -> None:
    cfg = Config()
    cfg.set_profile(Profile(name="a"))
    with pytest.raises(ConfigError, match="not found"):
        cfg.get("missing")


def test_config_get_no_profiles_raises() -> None:
    cfg = Config()
    with pytest.raises(ConfigError, match="no profiles"):
        cfg.get(None)


def test_load_missing_file_returns_empty_config(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "does-not-exist.toml")
    assert cfg.profiles == {}


def test_load_malformed_toml(tmp_path: Path) -> None:
    p = tmp_path / "bad.toml"
    p.write_text("not = valid = toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(p)


def test_resolve_key_explicit_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR_KEY, "from_env")
    p = Profile(name="x", key_ref="env:OTHER")
    assert resolve_key(p, explicit="boom") == "boom"


def test_resolve_key_env_var_wins_over_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR_KEY, "from_env")
    p = Profile(name="x", key_ref="env:OTHER")
    assert resolve_key(p) == "from_env"


def test_resolve_key_from_profile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    monkeypatch.setenv("MY_KEY", "secret-value")
    p = Profile(name="x", key_ref="env:MY_KEY")
    assert resolve_key(p) == "secret-value"


def test_resolve_key_missing_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    monkeypatch.delenv("MISSING", raising=False)
    p = Profile(name="x", key_ref="env:MISSING")
    with pytest.raises(AuthError, match="not set"):
        resolve_key(p)


def test_resolve_key_no_keyref_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    p = Profile(name="x", key_ref="")
    with pytest.raises(AuthError, match="no key_ref"):
        resolve_key(p)


def test_resolve_key_unknown_scheme_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    p = Profile(name="x", key_ref="sshagent:foo")
    with pytest.raises(AuthError, match="unknown key_ref scheme"):
        resolve_key(p)


def test_resolve_key_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ANVIL_KEY=dotenv-secret\n")
    p = Profile(name="x", key_ref=f"file:{env_file}:ANVIL_KEY")
    assert resolve_key(p) == "dotenv-secret"


def test_resolve_key_dotenv_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    p = Profile(name="x", key_ref="file:/nope/.env:ANVIL_KEY")
    with pytest.raises(AuthError, match="dotenv file not found"):
        resolve_key(p)


def test_resolve_key_dotenv_walk_finds_env_up_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    repo = tmp_path / "repo"
    nested = repo / "subdir" / "deeper"
    nested.mkdir(parents=True)
    (repo / ".env").write_text("ANVIL_UPLINK_KEY=walked-up\n")
    monkeypatch.chdir(nested)

    p = Profile(name="x", key_ref="dotenv:ANVIL_UPLINK_KEY")
    assert resolve_key(p) == "walked-up"


def test_resolve_key_dotenv_walk_no_env_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)

    p = Profile(name="x", key_ref="dotenv:ANVIL_UPLINK_KEY")
    with pytest.raises(AuthError, match="no .env found"):
        resolve_key(p)


def test_resolve_key_dotenv_walk_var_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    (tmp_path / ".env").write_text("OTHER_KEY=x\n")
    monkeypatch.chdir(tmp_path)

    p = Profile(name="x", key_ref="dotenv:ANVIL_UPLINK_KEY")
    with pytest.raises(AuthError, match="'ANVIL_UPLINK_KEY' not set"):
        resolve_key(p)


def test_resolve_key_from_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    import keyring

    class FakeBackend:
        def __init__(self) -> None:
            self.store: dict[tuple[str, str], str] = {}

        def get_password(self, service: str, username: str) -> str | None:
            return self.store.get((service, username))

        def set_password(self, service: str, username: str, pwd: str) -> None:
            self.store[(service, username)] = pwd

        def delete_password(self, service: str, username: str) -> None:
            self.store.pop((service, username), None)

        priority = 1

    fake = FakeBackend()
    fake.set_password("anvil-bridge", "myapp", "keyring-secret")
    monkeypatch.setattr(keyring, "get_password", fake.get_password)

    p = Profile(name="x", key_ref="keyring:anvil-bridge/myapp")
    assert resolve_key(p) == "keyring-secret"


def test_resolve_key_keyring_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    import keyring

    monkeypatch.setattr(keyring, "get_password", lambda s, u: None)
    p = Profile(name="x", key_ref="keyring:anvil-bridge/nothing")
    with pytest.raises(AuthError, match="no key stored"):
        resolve_key(p)


# --- Impersonation profile fields and resolvers ---------------------------


def test_profile_impersonate_fields_default() -> None:
    p = Profile.from_dict("alpha", {})
    assert p.impersonate_secret_ref == ""
    assert p.impersonate_callable == DEFAULT_IMPERSONATE_CALLABLE


def test_profile_roundtrip_with_impersonate_fields(tmp_path: Path) -> None:
    cfg = Config()
    cfg.set_profile(
        Profile(
            name="imp",
            key_ref="env:K",
            impersonate_secret_ref="dotenv:SHARED",
            impersonate_callable="_custom_dispatcher",
        )
    )
    p = tmp_path / "config.toml"
    save_config(cfg, p)
    loaded = load_config(p).profiles["imp"]
    assert loaded.impersonate_secret_ref == "dotenv:SHARED"
    assert loaded.impersonate_callable == "_custom_dispatcher"


def test_profile_elides_defaulted_impersonate_fields_on_save(tmp_path: Path) -> None:
    # Profiles without impersonation config must not pollute config.toml.
    cfg = Config()
    cfg.set_profile(Profile(name="plain", key_ref="env:K"))
    p = tmp_path / "config.toml"
    save_config(cfg, p)
    text = p.read_text(encoding="utf-8")
    assert "impersonate_secret_ref" not in text
    assert "impersonate_callable" not in text


def test_resolve_secret_dotenv_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    (repo / ".env").write_text("SHARED=shh\n")
    monkeypatch.chdir(nested)
    assert resolve_secret("dotenv:SHARED", "p", label="impersonate_secret") == "shh"


def test_resolve_secret_empty_ref_raises() -> None:
    with pytest.raises(AuthError, match="no impersonate_secret_ref"):
        resolve_secret("", "p", label="impersonate_secret")


def test_resolve_impersonate_secret_missing_ref_raises() -> None:
    p = Profile(name="x", key_ref="env:K")  # no impersonate_secret_ref
    with pytest.raises(ImpersonationError, match="no impersonate_secret_ref"):
        resolve_impersonate_secret(p)


def test_resolve_impersonate_secret_reads_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("SHARED=super-secret\n")
    monkeypatch.chdir(tmp_path)
    p = Profile(
        name="x",
        key_ref="env:K",
        impersonate_secret_ref="dotenv:SHARED",
    )
    assert resolve_impersonate_secret(p) == "super-secret"


# --- Hardening: impersonate_callable identifier validation ---


def test_from_dict_rejects_non_identifier_impersonate_callable() -> None:
    with pytest.raises(ConfigError, match="invalid impersonate_callable"):
        Profile.from_dict("x", {"impersonate_callable": "bad name"})


def test_from_dict_rejects_dotted_impersonate_callable() -> None:
    with pytest.raises(ConfigError, match="invalid impersonate_callable"):
        Profile.from_dict("x", {"impersonate_callable": "pkg.module.fn"})


def test_from_dict_accepts_valid_identifier() -> None:
    p = Profile.from_dict("x", {"impersonate_callable": "_my_shim2"})
    assert p.impersonate_callable == "_my_shim2"


def test_load_config_surfaces_invalid_impersonate_callable(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[profiles.x]\nkey_ref = "env:K"\nimpersonate_callable = "bad name"\n'
    )
    with pytest.raises(ConfigError, match="invalid impersonate_callable"):
        load_config(cfg)


# --- Hardening: dotenv-walk repo-root boundary ---


def test_dotenv_walk_stops_at_pyproject_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    # .env exists only ABOVE the repo marker — must NOT be read.
    (tmp_path / ".env").write_text("ANVIL_UPLINK_KEY=poisoned\n")
    repo = tmp_path / "repo"
    nested = repo / "sub"
    nested.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[tool.x]\n")
    monkeypatch.chdir(nested)

    p = Profile(name="x", key_ref="dotenv:ANVIL_UPLINK_KEY")
    with pytest.raises(AuthError, match="within the project boundary"):
        resolve_key(p)


def test_dotenv_walk_stops_at_git_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    (tmp_path / ".env").write_text("ANVIL_UPLINK_KEY=poisoned\n")
    repo = tmp_path / "repo"
    nested = repo / "sub"
    nested.mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.chdir(nested)

    p = Profile(name="x", key_ref="dotenv:ANVIL_UPLINK_KEY")
    with pytest.raises(AuthError, match="within the project boundary"):
        resolve_key(p)


def test_dotenv_walk_finds_env_inside_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    repo = tmp_path / "repo"
    nested = repo / "sub"
    nested.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[tool.x]\n")
    (repo / ".env").write_text("ANVIL_UPLINK_KEY=correct\n")
    monkeypatch.chdir(nested)

    p = Profile(name="x", key_ref="dotenv:ANVIL_UPLINK_KEY")
    assert resolve_key(p) == "correct"


# --- Hardening: SecretStr masks repr ---


def test_secretstr_repr_masks_value() -> None:
    s = SecretStr("actual-secret-abc123")
    assert repr(s) == "'***'"
    assert str(s) == "actual-secret-abc123"
    assert s == "actual-secret-abc123"


def test_secretstr_empty_repr() -> None:
    assert repr(SecretStr("")) == "''"


def test_resolve_key_returns_secretstr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("K_VAR", "the-key")
    monkeypatch.delenv(ENV_VAR_KEY, raising=False)
    p = Profile(name="x", key_ref="env:K_VAR")
    val = resolve_key(p)
    assert isinstance(val, SecretStr)
    assert "the-key" not in repr(val)


def test_resolve_impersonate_secret_returns_secretstr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("SHARED=shh\n")
    (tmp_path / "pyproject.toml").write_text("[tool.x]\n")
    monkeypatch.chdir(tmp_path)
    p = Profile(
        name="x", key_ref="env:K", impersonate_secret_ref="dotenv:SHARED"
    )
    val = resolve_impersonate_secret(p)
    assert isinstance(val, SecretStr)
    assert "shh" not in repr(val)
