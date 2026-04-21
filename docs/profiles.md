# Profiles

A **profile** is a named (app, URL, key-location) triple stored in `config.toml`. One profile per Anvil app you want to reach.

## Where the config lives

| OS | Path |
|---|---|
| Linux / WSL | `~/.config/anvil-bridge/config.toml` (or `$XDG_CONFIG_HOME/anvil-bridge/config.toml`) |
| macOS | `~/Library/Application Support/anvil-bridge/config.toml` |
| Windows | `%APPDATA%\anvil-bridge\config.toml` |

The file is chmod-600 on POSIX platforms. It holds profile metadata only — never the key itself.

## Shape of the file

```toml
[profiles.lat-profit]
url = "wss://anvil.works/uplink"
key_ref = "keyring:anvil-bridge/lat-profit"
default = true

[profiles.lat-badger]
url = "wss://anvil.works/uplink"
key_ref = "env:ANVIL_BRIDGE_KEY_LATBADGER"
default = false

[profiles.self-hosted]
url = "wss://anvil.example.com/_/uplink"
key_ref = "file:.env:ANVIL_KEY"
default = false
```

You can edit this file by hand, but `anvil-bridge init` is the path of least resistance — it also handles keyring/dotenv writes and `.gitignore` hygiene.

## Multi-app usage

Every command accepts `--profile <name>` (short `-p`):

```bash
anvil-bridge doctor --profile lat-profit
anvil-bridge call my_fn --profile lat-badger
anvil-bridge query items -p self-hosted --limit 10
```

If no `--profile` is given, the CLI picks:

1. The single profile marked `default = true`, if exactly one exists.
2. Otherwise, the only profile in the file, if there's only one.
3. Otherwise, it errors and tells you to pass `--profile` or set a default.

## Setting the default

Either edit `config.toml` directly or re-run `init`:

```bash
anvil-bridge init --profile lat-profit
```

The last profile created / updated becomes the default when it's the only one. To flip the default between existing profiles, hand-edit the `default = true` / `false` flags — there's no `anvil-bridge set-default` command yet.

## Non-interactive use (CI)

When you can't prompt for input — CI, containers, scripts — use:

```bash
anvil-bridge init \
  --profile prod \
  --non-interactive \
  --key-from-env ANVIL_BRIDGE_KEY_PROD
```

This writes a profile with `key_ref = "env:ANVIL_BRIDGE_KEY_PROD"`. No prompts; the default URL is used. You're responsible for exporting `ANVIL_BRIDGE_KEY_PROD` in the CI secret store before running commands.

## Key resolution order

When the CLI needs a key:

1. `$ANVIL_BRIDGE_KEY` (overrides everything — useful for ad-hoc runs).
2. The profile's `key_ref` (keyring → env → `.env` file).

Nothing reads `~/.netrc` or any other location.

## Self-hosted Anvil

Point `url` at your self-hosted uplink endpoint. The default path on a self-hosted Anvil install is usually `/_/uplink`, but check your deployment docs.

```toml
[profiles.internal]
url = "wss://anvil.internal.example.com/_/uplink"
key_ref = "keyring:anvil-bridge/internal"
default = false
```

## Deleting a profile

No command for it yet. Edit `config.toml` directly and delete the `[profiles.<name>]` block. If the key was in the keyring, also run:

```bash
keyring del anvil-bridge <profile-name>
```

(The `keyring` CLI ships with the `keyring` Python package — already a dependency of `anvil-uplink-cli`.)

## Inspecting the active profile

`anvil-bridge doctor` prints which profile it picked and which URL it connected to. Use it as a sanity check before running bulk operations:

```bash
anvil-bridge doctor -p lat-profit-prod
```
