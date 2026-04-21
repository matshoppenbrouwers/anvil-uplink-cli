# Security notes

`anvil-bridge` is a thin ergonomics layer over `anvil-uplink`. It does not add or remove privileges — whatever the key allows, the CLI allows. Read this page before pointing it at a production app.

## What a Server Uplink key grants

A Server Uplink key gives the holder the same authority as code running in a Server Module:

- Full read/write on every Data Table.
- The ability to invoke any `@anvil.server.callable` — including ones marked `require_user` (the Uplink is treated as a privileged caller).
- Access to `anvil.secrets`, `anvil.users`, `anvil.google.*`, etc., from inside the uplinked process.
- The ability to register reverse callables that Anvil will invoke on the uplink.

In short: **treat a Server Uplink key like a production database password.** Leaking it is equivalent to handing someone a root shell into your app's backend.

## What a Client Uplink key grants

A Client Uplink key roughly matches what a logged-in browser client can do:

- It can call `@anvil.server.callable` functions (unless they're `require_user=True` and no user is signed in).
- It cannot read Data Tables directly — `app_tables.x.search()` raises `PermissionDenied`.
- It cannot access server-only APIs like `anvil.secrets`.

Use Client Uplink for semi-trusted or user-owned contexts (an IoT device, a customer workstation, a public demo). `anvil-bridge doctor` reports which type it's talking to.

## Key storage

`anvil-bridge` never writes the key into its config file. The profile stores only a `key_ref` that points to where the key lives:

| `key_ref` scheme | Where the key lives |
|---|---|
| `keyring:<service>/<name>` | OS keyring — macOS Keychain, Windows Credential Manager, Secret Service on Linux |
| `env:<VAR>` | Environment variable (must be exported by your shell before running) |
| `file:<path>:<VAR>` | Dotenv file — variable `VAR` in the file at `<path>` |
| `dotenv:<VAR>` | Variable `VAR` in a `.env` found by walking up from CWD (recommended for agent workflows) |

**Keyring is the default and strongly preferred.** The OS keyring keeps the key encrypted at rest and scoped to the current user session. `env:`, `file:`, and `dotenv:` leave the key in plaintext somewhere; you are responsible for making sure those locations are protected.

When you choose the `dotenv` backend, `init` appends `.env` to `./.gitignore` automatically (if the `.env` lives inside your current working directory). If you move the file later, re-check your gitignore.

### `dotenv:` walk boundary

The `dotenv:` scheme walks from CWD toward the filesystem root and stops at the first of:

- a `.env` file (used), or
- a repo-root marker — `.git`, `pyproject.toml`, `setup.py`, or `setup.cfg` (walk stops, no `.env` used).

This keeps secret resolution scoped to the current project, so a planted `.env` in a parent directory outside the repo cannot poison loading. If you see an "no .env found ... within the project boundary" error, either add a `.env` inside the project or switch that profile to `keyring:` / `env:` / `file:`.

## Key resolution order

When a command needs the key, it tries these sources in order:

1. `--key` on the command line (not exposed on all commands yet; reserved).
2. `$ANVIL_BRIDGE_KEY` environment variable.
3. The profile's `key_ref` (keyring / env / file).

This means you can override a persisted profile on a single invocation without editing config:

```bash
ANVIL_BRIDGE_KEY=<other-key> anvil-bridge doctor --profile default
```

## Rotating a compromised key

If a key might be exposed:

1. In the Anvil Editor, open the Uplink panel and regenerate the key. The old one stops working immediately.
2. Re-run `anvil-bridge init --profile <name>` to overwrite the stored key with the new one.
3. `anvil-bridge doctor --profile <name>` should reconnect cleanly.

## Running against production vs. staging

Use separate profiles per environment. The profile name shows up in `doctor` output and in most error messages, so you always know which app you just connected to:

```bash
anvil-bridge init --profile lat-profit-staging
anvil-bridge init --profile lat-profit-prod
anvil-bridge doctor --profile lat-profit-prod
```

Consider marking staging as the default (`default = true` in `config.toml`) so a bare `anvil-bridge call ...` never lands in production by accident.

## What the CLI sends to Anvil

Every command opens a WebSocket to `profile.url` (default `wss://anvil.works/uplink`), authenticates with the resolved key, does its work, and disconnects. Nothing is logged remotely beyond what Anvil already logs for Server Module activity.

The CLI itself does not send telemetry anywhere. It's a local-only tool.

## What the CLI does NOT do

- It does not sanitize arguments before passing them to `anvil.server.call`. If your callable is `@anvil.server.callable` without its own validation, a malicious argument from the shell reaches it untouched — just like any other uplink caller.
- It does not re-verify the key on every command. Once a profile is pointed at a key, using that profile uses that key. If the key has been rotated in Anvil, the next command fails with an auth error (exit 40).
- It does not cache row data. Every `query` and `row` round-trips to Anvil.
