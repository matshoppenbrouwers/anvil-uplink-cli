# Security policy

## Supported versions

This project is pre-1.0 alpha. Only the latest released version on `main` is supported. Older tags will not receive backported fixes.

## Reporting a vulnerability

**Do not open a public GitHub issue** for suspected security vulnerabilities. Use one of the following instead:

1. **GitHub private security advisory** — preferred. Open a draft advisory at:
   <https://github.com/matshoppenbrouwers/anvil-uplink-cli/security/advisories/new>

2. **Email** — fallback if you cannot use GitHub: contact the maintainer via the email address on the commit history for this repo. Use subject line `anvil-uplink-cli security`.

Please include:

- A description of the issue and its impact.
- Steps to reproduce (or a proof-of-concept).
- Affected versions / commits.
- Any suggested remediation, if you have one.

## What's in scope

- Privilege escalation or secret leakage from the CLI itself (e.g. the `--as-user` impersonation flow, key/secret resolution via `keyring:` / `env:` / `file:` / `dotenv:`, config-file handling).
- Tampering avenues via the config file, environment, or `.env` walk.
- Dependency confusion or supply-chain concerns in the published package.
- Issues in the copy-pasted server helper template (`docs/impersonation.md`) that would surprise a developer who followed the documented setup.

## What's out of scope

- Misuse of a leaked uplink key or shared secret. A Server Uplink key grants Server Module-level authority by design; protecting it is the operator's responsibility.
- Denial-of-service against the local machine (the CLI runs locally and is subject to normal process-level limits).
- Third-party issues in `anvil-uplink`, `typer`, `rich`, `dotenv`, `platformdirs`, etc. — report those upstream. If an upstream issue materially affects this CLI's users, we'll pin or patch.

## Disclosure

The maintainer will acknowledge the report within 7 days. A fix-and-disclose window of up to 90 days is typical for pre-1.0 code; coordinated disclosure with reporters is preferred.
