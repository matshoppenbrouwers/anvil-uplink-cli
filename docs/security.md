# Security notes

Written up in Checkpoint 5. Headline rules:

- Server Uplink key = full Server Module privileges. Treat like a production credential.
- Prefer keyring over `.env`.
- `init` adds `.env` to `.gitignore` automatically.
- Use Client Uplink for untrusted systems (IoT, customer machines); it cannot read Data Tables by default.
