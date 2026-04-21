# Quickstart

Five minutes from nothing installed to a running REPL against your Anvil app.

## 1. Install

```bash
pip install git+https://github.com/matshoppenbrouwers/anvil-uplink-cli
```

Requires Python 3.10 or newer. Linux, macOS, WSL, and Windows (PowerShell or CMD) all work.

## 2. Get a Server Uplink key

In the Anvil Editor:

1. Click the **+** button in the sidebar → **Add Service** → **Uplink**.
2. Enable **Server Uplink** (grants full Server Module privileges).
3. Copy the key.

If you only need to invoke `@anvil.server.callable` functions and don't want broad access, use **Client Uplink** instead — most CLI commands still work, but `tables`, `query`, and `row` will return a permission error.

## 3. Create a profile

```bash
anvil-bridge init
```

The wizard asks for:

- **Profile name** — default is `default`. Use one per app (e.g., `lat-profit`, `lat-badger`).
- **Anvil URL** — default `wss://anvil.works/uplink`. Change this for self-hosted Anvil.
- **Key storage** — `keyring` (recommended), `env` (set `$VAR` yourself), or `dotenv` (write `VAR=key` to a `.env` file).

For `keyring` and `dotenv`, you're prompted for the key with hidden input. The key never appears in the config file.

## 4. Verify the connection

```bash
anvil-bridge doctor
```

This opens a connection, enumerates accessible tables, and reports which uplink type the key grants. A healthy Server Uplink looks like:

```
profile: default
url:     wss://anvil.works/uplink
connected: yes
uplink type: server
tables (3):
  • people
  • projects
  • invoices
```

Uplink type `client` is fine — it means the key is a Client Uplink, which means `tables` / `query` / `row` won't work, but `call`, `run`, and `repl` still do.

## 5. Start using it

```bash
anvil-bridge tables                              # list every Data Table + schema
anvil-bridge query projects --limit 5            # first 5 rows of `projects`
anvil-bridge query people --filter status=active # filter rows
anvil-bridge row projects <row-id>               # fetch one row
anvil-bridge call send_report 42                 # call @anvil.server.callable
anvil-bridge repl                                # interactive Python with uplink live
```

Every command accepts `--profile <name>` to target a specific app and `--json` for machine-readable output (pipeable into `jq`, shell scripts, or an AI assistant).

## Typical workflows

### Calling a server function with mixed arg types

```bash
anvil-bridge call create_invoice 42 --arg '["line1","line2"]' --kwarg due_days=30
```

Bare `42` → `int(42)`. `--arg` and `--kwarg` parse as JSON.

### Reading a JSON blob from stdin

```bash
cat payload.json | anvil-bridge call import_data --stdin
```

### Running a one-off diagnostic script

```bash
anvil-bridge run scripts/sanity_check.py
```

The script runs with `anvil`, `anvil.server`, and `app_tables` pre-imported and the connection already live.

## Next steps

- [`profiles.md`](profiles.md) — multi-app setups, self-hosted Anvil, non-interactive `init` for CI.
- [`security.md`](security.md) — what the key grants, how to store it safely, Server vs Client Uplink.
