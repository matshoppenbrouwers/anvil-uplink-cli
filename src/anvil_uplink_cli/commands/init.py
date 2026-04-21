"""`anvil-bridge init` — interactive profile wizard.

Flow:
1. Ask for profile name (default: first existing, or "default").
2. Ask for Anvil URL (default: wss://anvil.works/uplink).
3. Ask for key storage backend: keyring (recommended) or .env file.
4. Prompt for the Server Uplink key (hidden input).
5. Persist:
   - keyring backend: keyring.set_password(...) + profile.key_ref = "keyring:..."
   - .env backend: write VAR=<key> to ./.env, append .env to ./.gitignore, profile.key_ref = "file:.env:<VAR>"
6. Save config.toml.
7. Offer to run `doctor` next.

All prompts have sensible defaults so most users can accept everything.
"""
from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console

from anvil_uplink_cli._runner import run_or_exit
from anvil_uplink_cli.config import (
    DEFAULT_URL,
    KEYRING_SERVICE,
    Config,
    Profile,
    config_path,
    load_config,
    save_config,
    store_in_keyring,
)
from anvil_uplink_cli.errors import ConfigError

_console = Console()


def _default_profile_name(cfg: Config) -> str:
    if cfg.profiles:
        return next(iter(cfg.profiles))
    return "default"


def _slugify_env_var(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return f"ANVIL_UPLINK_KEY_{slug}" if slug else "ANVIL_UPLINK_KEY"


def _ensure_gitignore_entry(gitignore: Path, entry: str = ".env") -> bool:
    """Append `entry` to `gitignore` if missing. Returns True if it was added."""
    if not gitignore.exists():
        gitignore.write_text(f"{entry}\n", encoding="utf-8")
        return True
    existing = gitignore.read_text(encoding="utf-8").splitlines()
    stripped = [line.strip() for line in existing]
    if entry in stripped or f"/{entry}" in stripped:
        return False
    with gitignore.open("a", encoding="utf-8") as f:
        if existing and existing[-1].strip():
            f.write("\n")
        f.write(f"{entry}\n")
    return True


def _validate_dotenv_value(value: str) -> None:
    """Reject characters that would corrupt a KEY="value" assignment."""
    for bad, label in (('"', 'double-quote'), ("\\", "backslash"), ("\n", "newline"), ("\r", "carriage return")):
        if bad in value:
            raise ConfigError(
                f"uplink key contains a {label} character, which cannot be safely stored in a .env file; "
                "use the keyring backend instead"
            )


def _append_dotenv_var(dotenv: Path, var: str, value: str) -> None:
    _validate_dotenv_value(value)
    line = f'{var}="{value}"\n'
    if not dotenv.exists():
        dotenv.write_text(line, encoding="utf-8")
        return
    text = dotenv.read_text(encoding="utf-8")
    # Replace existing assignment to the same var, if any.
    pattern = re.compile(rf"^{re.escape(var)}=.*$", re.MULTILINE)
    if pattern.search(text):
        new_text = pattern.sub(f'{var}="{value}"', text)
    else:
        sep = "" if text.endswith("\n") or not text else "\n"
        new_text = f"{text}{sep}{line}"
    dotenv.write_text(new_text, encoding="utf-8")


def run(
    profile_name: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name (prompted if omitted).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Do not prompt; accept all defaults (requires --key-from-env).",
    ),
    key_from_env: str | None = typer.Option(
        None,
        "--key-from-env",
        help=(
            "Use env:VAR as the key_ref instead of prompting. "
            "Mainly for non-interactive use."
        ),
    ),
) -> None:
    run_or_exit(lambda: _init(profile_name, non_interactive, key_from_env))


def _prompt_key_ref(name: str) -> str:
    backend = typer.prompt(
        "Key storage (keyring / env / dotenv)", default="keyring"
    ).strip().lower()
    if backend == "keyring":
        secret = typer.prompt("Server Uplink key", hide_input=True)
        store_in_keyring(KEYRING_SERVICE, name, secret)
        return f"keyring:{KEYRING_SERVICE}/{name}"
    if backend == "env":
        env_var = typer.prompt("Env var name", default=_slugify_env_var(name))
        _console.print(
            f"[yellow]remember to set[/] [bold]{env_var}[/] in your shell before running commands"
        )
        return f"env:{env_var}"
    if backend in {"dotenv", "file", ".env"}:
        dotenv_path = Path(
            typer.prompt("Path to .env file", default="./.env")
        ).expanduser()
        var = typer.prompt("Variable name", default=_slugify_env_var(name))
        secret = typer.prompt("Server Uplink key", hide_input=True)
        _append_dotenv_var(dotenv_path, var, secret)
        # Best-effort .gitignore hygiene only when the .env is inside cwd.
        try:
            rel = dotenv_path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            rel = None
        if rel is not None:
            added = _ensure_gitignore_entry(Path.cwd() / ".gitignore", str(rel))
            if added:
                _console.print(f"[dim]added {rel} to .gitignore[/]")
        return f"file:{dotenv_path}:{var}"
    raise typer.BadParameter(
        f"unknown storage backend: {backend!r} (use keyring, env, or dotenv)"
    )


def _init(
    profile_name: str | None,
    non_interactive: bool,
    key_from_env: str | None,
) -> None:
    cfg = load_config()
    default_name = _default_profile_name(cfg)
    if profile_name:
        name = profile_name
    elif non_interactive:
        # Silently overwriting an existing profile in CI is a footgun.
        if cfg.profiles:
            raise typer.BadParameter(
                "--non-interactive requires --profile when profiles already exist"
            )
        name = default_name
    else:
        name = typer.prompt("Profile name", default=default_name)

    url = DEFAULT_URL if non_interactive else typer.prompt("Anvil uplink URL", default=DEFAULT_URL)

    if key_from_env:
        key_ref = f"env:{key_from_env}"
    elif non_interactive:
        raise typer.BadParameter("--non-interactive requires --key-from-env")
    else:
        key_ref = _prompt_key_ref(name)

    prof = Profile(name=name, url=url, key_ref=key_ref, default=(not cfg.profiles))
    cfg.set_profile(prof)
    written = save_config(cfg)
    _console.print(f"[green]saved profile[/] [bold]{name}[/] to [dim]{written}[/]")
    _console.print("next: run [bold]anvil-bridge doctor[/] to verify the connection")
