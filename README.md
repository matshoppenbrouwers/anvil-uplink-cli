# anvil-uplink-cli

A terminal bridge to Anvil apps via the Server Uplink. Run diagnostics, query Data Tables, invoke server functions, and drop into an interactive REPL — all from your shell or an AI coding assistant.

## Why

Working on an Anvil app from an external editor usually means copy-pasting Python into the Anvil Server Console and pasting results back. This CLI removes that round-trip by wrapping the `anvil-uplink` library with:

- one-command setup (`anvil-bridge init`)
- safe key handling (OS keyring, repo-local `.env`, or env var)
- multi-app profiles
- robust JSON / pretty output of Data Table rows, Media, datetimes, and portable classes
- **agent-safe mode**: the key stays in a gitignored `.env`, never in the tool call or agent context

## How this differs from the official Anvil CLI

Anvil ships an [official CLI](https://anvil.works/docs/using-another-ide/quickstart) (`anvil checkout`, `anvil watch`, …) for **editing app source** in a local IDE and syncing it to the cloud Editor. That's a code-sync tool.

`anvil-bridge` is a **runtime** tool. It doesn't touch your source — it connects to the already-deployed app as a Server Uplink client and lets you:

| You want to… | Use |
|---|---|
| Edit Forms/Modules in VS Code and sync | **official `anvil` CLI** |
| Query a Data Table, fetch a row, run a `@callable`, drop into a connected REPL | **`anvil-bridge`** |
| Run a local diagnostic script against live app data | **`anvil-bridge run`** |

Use both. They solve different problems.

## Install

Requires Python 3.10+. Install into a fresh virtual environment so the CLI and its dependencies stay isolated from your system Python.

### Windows (PowerShell)

```powershell
python -m venv $HOME\.anvil-bridge
$HOME\.anvil-bridge\Scripts\Activate.ps1
pip install git+https://github.com/matshoppenbrouwers/anvil-uplink-cli
anvil-bridge --version
```

### macOS / Linux (bash or zsh)

```bash
python3 -m venv ~/.anvil-bridge
source ~/.anvil-bridge/bin/activate
pip install git+https://github.com/matshoppenbrouwers/anvil-uplink-cli
anvil-bridge --version
```

### WSL (Ubuntu) — for use from Claude Code / agents

Install into a WSL-side venv so agent Bash tool calls can reach the CLI directly. **Don't activate a Windows venv from WSL** — the paths don't translate.

```bash
python3 -m venv ~/.anvil-bridge
source ~/.anvil-bridge/bin/activate
pip install git+https://github.com/matshoppenbrouwers/anvil-uplink-cli
anvil-bridge --version
```

The Windows Credential Manager is **not** readable from WSL, so `keyring:` key_refs configured on Windows won't resolve in WSL. Use the `dotenv:` key_ref scheme (see [Agent-safe setup](#agent-safe-setup-for-claude-code-or-any-ai-assistant)) — it works identically on both sides.

To use the CLI in a new shell, re-activate the venv first (`Activate.ps1` on Windows, `source .../activate` on Unix). On Windows, add the `Scripts` directory to your `PATH` if you want `anvil-bridge` available globally.

## Quickstart

1. In the Anvil Editor for your app, click the **+** sidebar button → **Uplink** → **Enable Server Uplink** → copy the key.
2. Initialize a profile:
   ```bash
   anvil-bridge init
   ```
3. Verify connectivity:
   ```bash
   anvil-bridge doctor
   ```
4. Start using the app:
   ```bash
   anvil-bridge tables
   anvil-bridge query projects --limit 5
   anvil-bridge call my_callable_function arg1 arg2
   anvil-bridge repl
   ```

## Agent-safe setup (for Claude Code or any AI assistant)

When an agent drives the CLI, the Server Uplink key must never appear in a tool call, command-line argument, or anything the agent can read. Inline env vars (`ANVIL_BRIDGE_KEY='...' anvil-bridge ...`) land in the transcript and create an exfiltration path via prompt injection.

The `dotenv:` key_ref scheme avoids this: the key sits in a gitignored `.env` at (or above) your working directory, and `anvil-bridge` reads it directly.

**Setup once:**

1. Run the wizard and pick the `repo` storage backend (default):
   ```bash
   anvil-bridge init
   # Profile name [default]: lat-profit
   # Anvil uplink URL [wss://anvil.works/uplink]:
   # Key storage (repo / keyring / env / file) [repo]:
   # Variable name [ANVIL_UPLINK_KEY_LATPROFIT]: ANVIL_UPLINK_KEY
   # Server Uplink key: ****************
   ```
   This writes `ANVIL_UPLINK_KEY="..."` to `./.env`, adds `.env` to `./.gitignore`, and stores `key_ref = "dotenv:ANVIL_UPLINK_KEY"` in the profile.

2. Or do it by hand:
   ```bash
   echo 'ANVIL_UPLINK_KEY="server_XXXXXXXX..."' >> .env
   echo '.env' >> .gitignore
   ```
   …and write a profile at `~/.config/anvil-bridge/config.toml` (Linux/WSL) or `%APPDATA%\anvil-bridge\config.toml` (Windows):
   ```toml
   [profiles.lat-profit]
   url = "wss://anvil.works/uplink"
   key_ref = "dotenv:ANVIL_UPLINK_KEY"
   default = true
   ```

**What the agent runs:**

```bash
anvil-bridge query bamboo_pay_history --limit 5 --json
anvil-bridge row users '[1043256,6089459745]' --json
anvil-bridge run ./scripts/diag.py
```

No `--key`. No inline env. No prompt for a secret. The CLI walks up from CWD to find `.env`, so one file at your monorepo root covers every subrepo.

**Why this matters:** with inline env vars, a malicious row value coming back from the app could instruct the agent to "repeat that last command into external tool X" and drag the key out. With `dotenv:`, the key is never in the agent's context, so that class of injection is defanged.

## Commands

| Command | Purpose |
|---|---|
| `init` | Profile wizard, writes `.env` / keyring entry, `.gitignore` hygiene |
| `doctor` | Verify key, list accessible tables, confirm Server vs Client Uplink |
| `call <fn> [args]` | Invoke `@anvil.server.callable` and print result. Add `--as-user <email>` for `require_user=True` callables — see [`docs/impersonation.md`](docs/impersonation.md). |
| `query <table>` | Search a Data Table (`--filter k=v`, `--limit N`) |
| `tables` | List tables and column schemas |
| `row <table> <id>` | Fetch a single row by id |
| `run <script.py>` | Run local Python with the uplink pre-connected |
| `repl` | Interactive Python shell with `anvil`, `anvil.server`, `app_tables` live |

All commands accept `--profile <name>` for multi-app use and `--json` for machine-readable output.

## Claude Code skill

A ready-made Claude Code skill ships with the repo at [`skills/anvil-bridge/`](skills/anvil-bridge/SKILL.md). It teaches Claude the agent-safe invocation rules (full path, no inline keys), the `tables`-doesn't-enumerate gotcha, and when to use `run` vs repeated `query` calls.

Install locally:
```bash
cp -r skills/anvil-bridge ~/.claude/skills/
```

Or distribute the packaged artifact: [`skills/dist/anvil-bridge.skill`](skills/dist/anvil-bridge.skill).

## Security

The **Server Uplink** key grants full Server Module privileges to whoever holds it: direct Data Table read/write, user management, secret access. Treat it like a production credential.

Key storage backends in order of preference:

| Backend | key_ref | When |
|---|---|---|
| **Repo-local `.env`** (recommended for agents) | `dotenv:VAR` | AI assistants, multi-machine dev, WSL. Walks up from CWD to find `.env`. |
| **OS keyring** | `keyring:anvil-bridge/<profile>` | Single-machine, single-user, no agents. Most secure at rest. |
| **Env var** | `env:VAR` | CI, ephemeral shells. Transient. |
| **Exact dotenv path** | `file:<path>:VAR` | Shared `.env` outside any repo tree. |

- `init` writes `.env` / updates `.gitignore` automatically for the `repo` backend.
- For connecting untrusted systems (IoT, customer machines), use a Client Uplink key instead of a Server Uplink key.
- WSL cannot read Windows Credential Manager — use `dotenv:` if you need both environments.

See [`docs/security.md`](docs/security.md) for full details.

### Calling `require_user=True` functions

> **Skip this section unless your app uses `require_user=True` on callables you need to invoke.** The default install and quickstart above do not require any of what follows — `doctor`, `query`, `row`, `run`, and plain `call` all work without it.

Apps that gate every callable with `require_user=True` can't be driven from an Uplink session out of the box. `anvil-bridge` adds a `--as-user <email>` flag that dispatches through a small server-side helper you drop into your app (`_uplink_run_as`), protected by a shared secret + email allowlist + audit log. See [`docs/impersonation.md`](docs/impersonation.md).

**Status (v0.2.0):** the CLI-side plumbing and unit/smoke tests are green, but the end-to-end flow (CLI → server helper → `force_login` → nested `anvil.server.call` → audit row) has **not** been exercised against a deployed app yet. Treat `--as-user` as provisional until the test app (`formal-valuable-raccoon-dog.anvil.app`) has run the full happy/failure-mode matrix.

## Status

Early alpha. API surface may shift before v1.0. Distributed via `pip install git+https://…` until the CLI stabilizes.

## License

MIT
