"""Profile management: TOML config + key resolution.

Config file lives at platformdirs.user_config_dir("anvil-bridge") / "config.toml".
Keys are never written into the config file — only references to where the key
lives (keyring service, env var name, or a path to a dotenv + variable name).

Key resolution order:
    1. explicit --key flag (or ANVIL_BRIDGE_KEY env var)
    2. profile.key_ref:
         keyring:<service>/<name>
         env:<VAR_NAME>
         file:<path>:<VAR_NAME>     (exact dotenv path)
         dotenv:<VAR_NAME>          (walk up from CWD to find .env)

The key ref scheme is:
    keyring:anvil-bridge/lat-profit
    env:ANVIL_BRIDGE_KEY_LATPROFIT
    file:.env:ANVIL_UPLINK_KEY
    dotenv:ANVIL_UPLINK_KEY          (recommended — agent-safe, repo-local)
"""
from __future__ import annotations

import os
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import tomli_w
from dotenv import dotenv_values, find_dotenv
from platformdirs import user_config_dir

# tomllib is stdlib in 3.11+, tomli is the backport for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — CI covers both paths
    import tomli as tomllib  # type: ignore[import-not-found]

from anvil_uplink_cli.errors import AuthError, ConfigError, ImpersonationError

DEFAULT_URL = "wss://anvil.works/uplink"
ENV_VAR_KEY = "ANVIL_BRIDGE_KEY"
CONFIG_FILENAME = "config.toml"
KEYRING_SERVICE = "anvil-bridge"
DEFAULT_IMPERSONATE_CALLABLE = "_uplink_run_as"


def config_path() -> Path:
    """Resolve the platform-specific config file path."""
    return Path(user_config_dir("anvil-bridge", appauthor=False)) / CONFIG_FILENAME


@dataclass
class Profile:
    name: str
    url: str = DEFAULT_URL
    key_ref: str = ""
    default: bool = False
    impersonate_secret_ref: str = ""
    impersonate_callable: str = DEFAULT_IMPERSONATE_CALLABLE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        del d["name"]  # name is the table key, not a field
        # Elide defaulted optional fields so existing profiles round-trip cleanly.
        if not d["impersonate_secret_ref"]:
            del d["impersonate_secret_ref"]
        if d["impersonate_callable"] == DEFAULT_IMPERSONATE_CALLABLE:
            del d["impersonate_callable"]
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> Profile:
        return cls(
            name=name,
            url=str(data.get("url", DEFAULT_URL)),
            key_ref=str(data.get("key_ref", "")),
            default=bool(data.get("default", False)),
            impersonate_secret_ref=str(data.get("impersonate_secret_ref", "")),
            impersonate_callable=str(
                data.get("impersonate_callable", DEFAULT_IMPERSONATE_CALLABLE)
            ),
        )


@dataclass
class Config:
    profiles: dict[str, Profile] = field(default_factory=dict)

    def get(self, name: str | None) -> Profile:
        if name:
            if name not in self.profiles:
                raise ConfigError(f"profile '{name}' not found in {config_path()}")
            return self.profiles[name]
        defaults = [p for p in self.profiles.values() if p.default]
        if len(defaults) == 1:
            return defaults[0]
        if len(defaults) > 1:
            raise ConfigError(
                f"multiple default profiles: {', '.join(p.name for p in defaults)}"
            )
        if len(self.profiles) == 1:
            return next(iter(self.profiles.values()))
        if not self.profiles:
            raise ConfigError(
                "no profiles configured — run `anvil-bridge init` to create one"
            )
        raise ConfigError(
            "no default profile — pass --profile <name> or mark one default=true"
        )

    def set_profile(self, profile: Profile) -> None:
        if profile.default:
            for other in self.profiles.values():
                other.default = False
        self.profiles[profile.name] = profile


def load_config(path: Path | None = None) -> Config:
    p = path or config_path()
    if not p.exists():
        return Config()
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid TOML in {p}: {e}") from e
    profiles_tbl = data.get("profiles", {})
    if not isinstance(profiles_tbl, dict):
        raise ConfigError(f"'profiles' in {p} must be a table")
    profiles = {
        name: Profile.from_dict(name, raw)
        for name, raw in profiles_tbl.items()
        if isinstance(raw, dict)
    }
    return Config(profiles=profiles)


def save_config(cfg: Config, path: Path | None = None) -> Path:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"profiles": {name: prof.to_dict() for name, prof in cfg.profiles.items()}}
    with p.open("wb") as f:
        tomli_w.dump(data, f)
    with suppress(OSError):
        p.chmod(0o600)  # best-effort; Windows may not support POSIX permissions
    return p


def resolve_secret(ref: str, profile_name: str, *, label: str = "secret") -> str:
    """Resolve a reference string via the shared scheme dispatcher.

    Used for both the uplink key and any other per-profile secret (e.g. the
    impersonation shared secret). Raises AuthError on failure.

    Supported schemes:
        keyring:<service>/<name>
        env:<VAR>
        file:<path>:<VAR>
        dotenv:<VAR>
    """
    ref = ref.strip()
    if not ref:
        raise AuthError(
            f"profile '{profile_name}' has no {label}_ref configured"
        )
    scheme, _, rest = ref.partition(":")
    if scheme == "keyring":
        return _load_from_keyring(rest, profile_name, label=label)
    if scheme == "env":
        val = os.environ.get(rest)
        if not val:
            raise AuthError(
                f"env var '{rest}' is not set (profile '{profile_name}', {label})"
            )
        return val
    if scheme == "file":
        return _load_from_file(rest, profile_name, label=label)
    if scheme == "dotenv":
        return _load_from_dotenv_walk(rest, profile_name, label=label)
    raise AuthError(
        f"unknown {label}_ref scheme '{scheme}' in profile '{profile_name}'"
    )


def resolve_key(profile: Profile, explicit: str | None = None) -> str:
    """Resolve the uplink key for a profile. Raises AuthError on failure."""
    if explicit:
        return explicit
    env_key = os.environ.get(ENV_VAR_KEY)
    if env_key:
        return env_key
    ref = profile.key_ref.strip()
    if not ref:
        raise AuthError(
            f"profile '{profile.name}' has no key_ref — "
            f"set it via `anvil-bridge init` or pass --key"
        )
    return resolve_secret(ref, profile.name, label="key")


def resolve_impersonate_secret(profile: Profile) -> str:
    """Resolve the shared impersonation secret for a profile.

    Raises ImpersonationError if the profile has no impersonate_secret_ref,
    so --as-user fails cleanly with a dedicated exit code rather than
    leaking through as a generic auth error.
    """
    ref = profile.impersonate_secret_ref.strip()
    if not ref:
        raise ImpersonationError(
            f"profile '{profile.name}' has no impersonate_secret_ref — "
            f"add it to ~/.config/anvil-bridge/config.toml and put the "
            f"shared secret in your .env. See docs/impersonation.md."
        )
    return resolve_secret(ref, profile.name, label="impersonate_secret")


def _load_from_keyring(rest: str, profile_name: str, *, label: str = "key") -> str:
    # rest format: "<service>/<key_name>"
    if "/" in rest:
        service, _, username = rest.partition("/")
    else:
        service, username = KEYRING_SERVICE, rest
    try:
        import keyring
    except ImportError as e:
        raise AuthError(f"keyring not installed: {e}") from e
    try:
        val = keyring.get_password(service, username)
    except Exception as e:
        raise AuthError(f"keyring access failed: {e}") from e
    if not val:
        raise AuthError(
            f"no {label} stored in keyring for {service}/{username} "
            f"(profile '{profile_name}') — re-run `anvil-bridge init`"
        )
    return val


def _load_from_file(rest: str, profile_name: str, *, label: str = "key") -> str:
    # rest format: "<path>:<VAR_NAME>"
    path_str, _, var_name = rest.rpartition(":")
    if not path_str or not var_name:
        raise AuthError(
            f"malformed file: {label}_ref '{rest}' (expected 'file:<path>:<VAR>')"
        )
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        # dotenv files are typically in the project root
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        raise AuthError(f"dotenv file not found: {p} (profile '{profile_name}')")
    values = dotenv_values(p)
    val = values.get(var_name)
    if not val:
        raise AuthError(
            f"'{var_name}' not set in {p} (profile '{profile_name}', {label})"
        )
    return val


def _load_from_dotenv_walk(
    var_name: str, profile_name: str, *, label: str = "key"
) -> str:
    """Walk up from CWD looking for `.env`; read `var_name` from it.

    This is the agent-safe default: the secret only lives in the repo's
    (gitignored) .env, never on the command line or in an env var that the
    caller had to type.
    """
    var_name = var_name.strip()
    if not var_name:
        raise AuthError(
            f"malformed dotenv: {label}_ref (expected 'dotenv:<VAR>')"
        )
    found = find_dotenv(usecwd=True)
    if not found:
        raise AuthError(
            f"no .env file found walking up from {Path.cwd()} "
            f"(profile '{profile_name}', {label})"
        )
    values = dotenv_values(found)
    val = values.get(var_name)
    if not val:
        raise AuthError(
            f"'{var_name}' not set in {found} (profile '{profile_name}', {label})"
        )
    return val


def store_in_keyring(service: str, username: str, secret: str) -> None:
    """Best-effort keyring write; raises AuthError on failure."""
    try:
        import keyring
    except ImportError as e:
        raise AuthError(f"keyring not installed: {e}") from e
    try:
        keyring.set_password(service, username, secret)
    except Exception as e:
        raise AuthError(f"keyring write failed: {e}") from e
