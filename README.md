# anvil-uplink-cli

A terminal bridge to Anvil apps via the Server Uplink. Run diagnostics, query Data Tables, invoke server functions, and drop into an interactive REPL — all from your shell or an AI coding assistant.

## Why

Working on an Anvil app from an external editor usually means copy-pasting Python into the Anvil Server Console and pasting results back. This CLI removes that round-trip by wrapping the `anvil-uplink` library with:

- one-command setup (`anvil-bridge init`)
- safe key handling (OS keyring or `.env`)
- multi-app profiles
- robust JSON / pretty output of Data Table rows, Media, datetimes, and portable classes

## Install

```bash
pip install git+https://github.com/matshoppenbrouwers/anvil-uplink-cli
```

Requires Python 3.10+. Works on Linux, macOS, WSL, and Windows (PowerShell).

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

## Commands

| Command | Purpose |
|---|---|
| `init` | Profile wizard, writes `.env` / keyring entry, `.gitignore` hygiene |
| `doctor` | Verify key, list accessible tables, confirm Server vs Client Uplink |
| `call <fn> [args]` | Invoke `@anvil.server.callable` and print result |
| `query <table>` | Search a Data Table (`--filter k=v`, `--limit N`) |
| `tables` | List tables and column schemas |
| `row <table> <id>` | Fetch a single row by id |
| `run <script.py>` | Run local Python with the uplink pre-connected |
| `repl` | Interactive Python shell with `anvil`, `anvil.server`, `app_tables` live |

All commands accept `--profile <name>` for multi-app use and `--json` for machine-readable output.

## Security

The **Server Uplink** key grants full Server Module privileges to whoever holds it: direct Data Table read/write, user management, secret access. Treat it like a production credential.

- Prefer storing keys in your OS keyring (the default; handled by `init`).
- If using `.env`, make sure it's in `.gitignore` (`init` handles this automatically).
- For connecting untrusted systems (IoT, customer machines), use a Client Uplink key instead.

See [`docs/security.md`](docs/security.md) for full details.

## Status

Early alpha. API surface may shift before v1.0. Distributed via `pip install git+https://…` until the CLI stabilizes.

## License

MIT
