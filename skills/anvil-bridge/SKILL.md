---
name: anvil-bridge
description: Inspect live Anvil Data Tables and invoke server callables from the terminal via the anvil-uplink-cli tool (`anvil-bridge`). Use when the user references an Anvil app, asks to query/read/inspect a Data Table row, needs to call an `@anvil.server.callable` function against a deployed app, or mentions files like `anvil.yaml` / `server_code/*.py` and wants live data. Covers correct binary invocation, agent-safe key handling (never pass the key inline), profile selection, and the `tables`-doesn't-enumerate gotcha. Requires the user to have `anvil-uplink-cli` installed and a configured profile.
---

# anvil-bridge

`anvil-bridge` is a CLI that opens an Anvil Server Uplink connection and exposes Data Table access and server-callable invocation from the shell. Use it instead of pasting Python into the Anvil Server Console.

Source: https://github.com/matshoppenbrouwers/anvil-uplink-cli

## Critical rules (read first)

1. **Call by full path.** The CLI lives in a dedicated venv that is NOT on `PATH` in fresh Bash subshells (Claude Code spawns one per tool call). Calling `anvil-bridge` bare will usually fail with "command not found".
   - Default install path: `~/.anvil-bridge/bin/anvil-bridge` (absolute: `/home/<user>/.anvil-bridge/bin/anvil-bridge` on Linux/WSL).
   - Discover it: `ls ~/.anvil-bridge/bin/anvil-bridge 2>/dev/null || which anvil-bridge`.

2. **NEVER pass the Uplink key inline.** Not as `--key ...`, not as `ANVIL_BRIDGE_KEY=... anvil-bridge ...`. The key lands in the transcript and creates a prompt-injection exfiltration path. The CLI resolves the key from a `.env` ancestor via `dotenv:ANVIL_UPLINK_KEY` — it works silently, do not interfere with it. Also do NOT `cat .env` or read the key file.

3. **Run from inside a directory with a `.env` ancestor.** The CLI walks up from CWD looking for `.env`. If the user's shell is in a directory with no `.env` above it, the key won't resolve — `cd` into the relevant repo first (or tell the user to).

4. **Prefer `--json`** when the output is for parsing or passing to another tool. Pretty-printed tables are for humans and get garbled in agent transcripts.

## First call in any session

Always verify the connection works before querying:

```bash
<BRIDGE> doctor
```

Expected output includes `connected: yes` and the configured profile. If it fails:
- `auth error` → key isn't resolving; user needs a `.env` with `ANVIL_UPLINK_KEY` at or above CWD, or a configured profile. Do NOT try to fix by passing the key inline.
- `command not found` → you used bare `anvil-bridge` instead of the full path.
- `connection refused` / timeout → Anvil Server Uplink isn't enabled in the app's Editor; user has to fix in the Anvil UI.

Replace `<BRIDGE>` with the full binary path (see rule 1).

## Common invocations

```bash
<BRIDGE> doctor --profile <name>                              # verify connection
<BRIDGE> query <table> --profile <name> --limit 5 --json      # sample rows, JSON
<BRIDGE> query <table> --profile <name> --columns a,b,c       # narrow pretty output
<BRIDGE> query <table> --profile <name> --filter status=done  # server-side filter
<BRIDGE> row <table> '<row_id>' --profile <name> --json       # one row by id
<BRIDGE> call <fn> --profile <name> arg1 --kwarg k=v          # @anvil.server.callable
<BRIDGE> call <fn> --as-user <svc-email> --profile <name>     # for require_user=True (see section below)
<BRIDGE> run /tmp/diag.py --profile <name>                    # run local script with uplink
```

`--profile <name>` is optional if a default profile is set in `~/.config/anvil-bridge/config.toml`. Note that `--profile` goes AFTER the subcommand, not before it.

## The `tables` gotcha

`<BRIDGE> tables` does **not** return the list of tables. This is a limitation of the underlying `anvil-uplink` library: `app_tables` is a lazy proxy whose `__dir__` returns only `['cache']`, not the actual table names. The command will run without error but give useless output.

**To get the list of table names, read them from the repo's `anvil.yaml`** — the `db_schema:` section lists every table. Then pass the names you need to `query` / `row`.

```bash
# Find table names from the repo, not from the wire
grep -A2 'db_schema:' anvil.yaml | head -40
```

## When to use `run` instead of repeated `query`

For any diagnostic that touches >1 table, does aggregations, or needs cross-row logic, write a local Python script to `/tmp/diag.py` and execute it with `<BRIDGE> run /tmp/diag.py`. Benefits:
- One uplink connection (saves ~500ms per query)
- Real Python: `statistics.mean`, `collections.Counter`, joins, etc.
- Cleaner output than chaining `--json` through `jq`

See [references/diagnostic-template.py](references/diagnostic-template.py) for a starting point.

## Invoking callables that require a user

Callables decorated with `@anvil.server.callable(require_user=True)` reject direct Uplink calls — Uplink sessions have no logged-in user, so the gate slams shut. Use `--as-user <email>` to dispatch through the app's `_uplink_run_as` helper, which does `anvil.users.force_login(...)` server-side before calling the target.

```bash
<BRIDGE> call <fn> --as-user <service-account-email> --profile <name>
<BRIDGE> call <fn> --as-user <service-account-email> --kwarg project_code=DEMO --json
```

**Requirements (app-side, set up once per app):**
- The app has `_uplink_run_as` installed in `server_code/` (template + setup in `docs/impersonation.md`)
- `anvil_uplink_shared_secret` exists in the app's Secrets
- `uplink_audit` data table exists
- A service-account user exists whose email suffix is in the helper's allowlist

**Requirements (CLI-side, in the profile):**
- `impersonate_secret_ref = "dotenv:ANVIL_UPLINK_SHARED_SECRET"` in the profile
- `ANVIL_UPLINK_SHARED_SECRET=...` in the same `.env` as the uplink key

If either side isn't set up, the CLI exits with code `42` (missing `impersonate_secret_ref`) or the server-side helper raises `PermissionError` (bad secret / non-allowlisted email) which surfaces as exit `30`. Never impersonate real customer accounts — keep the allowlist to service-account emails only.

Full setup: see `docs/impersonation.md` in the `anvil-uplink-cli` repo.

## Row cell access gotcha

Inside a `run` script, Anvil `Row` objects require bracket notation:
- `row['field']` — correct
- `row.get('field')` — raises `AttributeError`
- `'field' in row` — raises; check `row['field'] is None` instead

Iterating a row yields `[key, value]` lists, not keys.

## What NOT to do

- Don't `cat .env` or `grep -r "ANVIL_" .env` — the key must stay out of your context.
- Don't inline `ANVIL_BRIDGE_KEY=...` as a one-off even "for debugging."
- Don't `source ~/.anvil-bridge/bin/activate` — Bash tool calls get fresh shells, activation doesn't persist. Full path always.
- Don't assume `tables` works; use `anvil.yaml`.
- Don't run `repl` in an agent session; it needs a TTY you don't have.

## When the tool isn't installed

If `~/.anvil-bridge/bin/anvil-bridge` does not exist, tell the user to install it — do NOT try to install it silently:

```bash
python3 -m venv ~/.anvil-bridge
~/.anvil-bridge/bin/pip install git+https://github.com/matshoppenbrouwers/anvil-uplink-cli
~/.anvil-bridge/bin/anvil-bridge init
```

The `init` wizard is interactive and can't be driven from a tool call. Let the user run it.
