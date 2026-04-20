# Profiles

Full profile docs coming in Checkpoint 5.

Profiles live at:
- Linux/WSL: `~/.config/anvil-bridge/config.toml`
- macOS: `~/Library/Application Support/anvil-bridge/config.toml`
- Windows: `%APPDATA%\anvil-bridge\config.toml`

Key resolution order: `--key` flag → `ANVIL_BRIDGE_KEY` env var → profile's `key_ref` (keyring → env → `.env`).
