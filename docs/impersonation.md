# `--as-user` impersonation

`anvil-bridge call --as-user <email> <fn>` invokes a server-callable **as if** the named user were logged in. It exists so you can call functions guarded by `@anvil.server.callable(require_user=True)` from the Uplink, where no user session exists by default.

This is opt-in on both sides: the CLI ships the flag, but each app has to drop in a small server-side helper and wire it to a shared secret before the flow works.

## Intended use

This feature is intended for developers operating their own Anvil apps. Using it against an app you do not own or have explicit written permission to administer likely violates computer-misuse legislation in your jurisdiction (UK CMA 1990, US CFAA, EU NIS2, and local equivalents). The authors and contributors disclaim responsibility for unauthorized use.

## Why this exists

Every callable decorated with `require_user=True` rejects Uplink calls with:

```
server raised AnvilWrappedError: You must be logged in to call this server function
```

The Uplink is an authenticated channel for your *code*, not for an end user. There's no session, so `anvil.users.get_user()` returns `None` and `require_user` slams the door.

`--as-user` closes this gap via **one server-side RPC** that does `anvil.users.force_login(...)` and then dispatches the target function in the same worker session. The login state propagates into the nested `anvil.server.call`, so `require_user` is satisfied.

## Security model

Three overlapping guards — all required:

1. **Server Uplink key** — gates reaching the helper at all. Never pass `--key` or inline env vars (see `docs/security.md`); the `dotenv:` scheme keeps it out of the transcript.
2. **Shared secret** — proves the request came from something that holds more than just the uplink key. Rejected by the helper before any login attempt. Stored next to the uplink key in `.env`.
3. **Email allowlist** — the helper refuses to `force_login` any email whose suffix isn't in its allowlist. Keep this to **service-account emails only** so a compromised uplink key + shared secret still cannot act as any real customer.

**Threat framing.** If both the uplink key and the shared secret are exposed, an attacker can impersonate every email on the allowlist. The allowlist is what keeps that blast radius small. Never put customer email domains in it.

**Revocation.** Rotate the shared secret in the app's `anvil.secrets` and update `.env` locally. Clients that don't know the new secret fail with `server raised PermissionError: invalid shared secret` — no CLI change required.

## Server-side helper (drop into your app)

Create `server_code/uplink_helpers.py` in your app and paste this verbatim, then edit the `_ALLOWED_EMAIL_SUFFIXES` tuple for your app's service-account email domain. This template is provided under this project's MIT license — pasting it into your app is allowed; if you maintain a third-party-licenses file, credit this project per MIT §3.

```python
import datetime
import hmac
import anvil.secrets
import anvil.server
import anvil.users
from anvil.tables import app_tables

# Edit this for your app. Example: ("@yourcompany-ops.internal",)
# Every entry MUST start with "@" — the assert below enforces this so a
# copy-paste mistake like ("company.com",) cannot silently match
# "attacker@evil.company.com".
# MUST be non-empty — an empty tuple rejects all impersonation attempts.
_ALLOWED_EMAIL_SUFFIXES = ()
assert all(s.startswith("@") for s in _ALLOWED_EMAIL_SUFFIXES), (
    "_ALLOWED_EMAIL_SUFFIXES entries must start with '@'"
)


@anvil.server.callable
def _uplink_run_as(shared_secret, email, fn_name, args=None, kwargs=None):
    """Impersonate a service-account user and dispatch fn_name.

    Server-Uplink-only; requires the shared secret; allowlist-gated; audited.
    """
    rc = getattr(anvil.server.context, "remote_caller", None)
    if rc is None or rc.type != "uplink" or not getattr(rc, "is_trusted", False):
        raise PermissionError("_uplink_run_as: server-uplink-only")

    expected = anvil.secrets.get_secret("anvil_uplink_shared_secret")
    if not isinstance(shared_secret, str) or not hmac.compare_digest(
        shared_secret, expected
    ):
        raise PermissionError("_uplink_run_as: invalid shared secret")

    if not isinstance(email, str):
        raise PermissionError("_uplink_run_as: email must be a string")
    email_lc = email.lower()
    if not _ALLOWED_EMAIL_SUFFIXES or not any(
        email_lc.endswith(suffix.lower()) for suffix in _ALLOWED_EMAIL_SUFFIXES
    ):
        raise PermissionError(
            f"_uplink_run_as: {email} not in impersonable allowlist"
        )

    user = app_tables.users.get(email=email)
    if not user:
        raise LookupError(f"_uplink_run_as: user {email} not found")

    audit_row = app_tables.uplink_audit.add_row(
        ts=datetime.datetime.utcnow(),
        impersonated_email=email,
        fn_name=fn_name,
        caller_ip=getattr(
            getattr(anvil.server.context, "client", None), "ip", None
        ),
        result_status="attempted",
        error_message="",
    )
    try:
        anvil.users.force_login(user, remember=False)  # remember=False is required
        result = anvil.server.call(fn_name, *(args or []), **(kwargs or {}))
        audit_row["result_status"] = "ok"
        return result
    except Exception as exc:
        audit_row["result_status"] = "error"
        # repr() avoids attacker-controlled f-string surprises from exc.__str__
        audit_row["error_message"] = repr(exc)[:500]
        raise
    finally:
        try:
            anvil.users.logout()
        except Exception:
            pass
```

### What each guard does

| Line | Guard | If it fails |
|------|-------|-------------|
| `remote_caller.type != "uplink" or not is_trusted` | rejects calls from Forms, server modules, or **Client** Uplinks — only a trusted **Server** Uplink passes | `PermissionError: server-uplink-only` |
| shared-secret check | ensures caller isn't just holding the uplink key | `PermissionError: invalid shared secret` |
| allowlist check | blocks impersonation of anyone outside the service-account domain | `PermissionError: ... not in impersonable allowlist` |
| `user` lookup | typo / missing user | `LookupError: user <email> not found` |
| `remember=False` on `force_login` | avoids writing a persistent session cookie for the uplink-only impersonation | — |
| `logout()` in `finally` | cleans up server-side session state | — |
| two-phase audit row | logs `attempted` before dispatch, updates to `ok` / `error` after | crashes still leave a trace |

## App setup

Once per app, in the Anvil Editor (or via a commit to the app repo):

1. **Add the shared secret.** In your app's Secrets (Gear icon → Secrets):
   ```
   Name:  anvil_uplink_shared_secret
   Value: <generate locally with: openssl rand -hex 32>
   ```
2. **Create the audit table.** Data Tables → new table `uplink_audit` with columns:

   | Column | Type |
   |---|---|
   | `ts` | datetime |
   | `impersonated_email` | text |
   | `fn_name` | text |
   | `caller_ip` | text |
   | `result_status` | text (`attempted` / `ok` / `error`) |
   | `error_message` | text |

   Set "Forms" access to **None** and "Server code" access to **Full**.
3. **Create the service-account user.** In the `users` table, add a row with an email whose suffix matches what you set in `_ALLOWED_EMAIL_SUFFIXES`. Give it whatever auxiliary rows your `require_user` callables actually check (roles, team memberships, etc.) — impersonation hands over that user's privileges wholesale.
4. **Deploy.** Commit, push, and hit Publish (or run the app).

## CLI config

Add `impersonate_secret_ref` to your profile in `~/.config/anvil-bridge/config.toml`:

```toml
[profiles.my-app]
url = "wss://anvil.works/uplink"
key_ref = "dotenv:ANVIL_UPLINK_KEY"
impersonate_secret_ref = "dotenv:ANVIL_UPLINK_SHARED_SECRET"
default = true
```

Put the shared secret in the same `.env` the uplink key lives in:

```
ANVIL_UPLINK_KEY="server_XXXX..."
ANVIL_UPLINK_SHARED_SECRET="<the openssl rand -hex 32 value>"
```

The `dotenv:` scheme walks up from CWD to find this file, same as the uplink key. Both secrets share one trust boundary (the `.env`), so there's no new storage decision to make.

### Custom dispatcher name

If you don't want to name the server helper `_uplink_run_as`, add:

```toml
impersonate_callable = "my_custom_dispatcher_name"
```

to the profile. The server function signature must still be `(shared_secret, email, fn_name, args, kwargs)`.

## Usage

```bash
anvil-bridge call --as-user svc@yourapp-ops.internal get_project_list

# with args / kwargs — they forward through the dispatcher unchanged
anvil-bridge call --as-user svc@yourapp-ops.internal find_project \
    --kwarg project_code=DEMO --kwarg year=2026

# --json still works; wraps the inner function's return value
anvil-bridge call --as-user svc@yourapp-ops.internal get_dashboard --json
```

Short form: `-u` is equivalent to `--as-user`.

## Exit codes

| Code | Cause |
|------|-------|
| `42` | CLI-side: profile has no `impersonate_secret_ref` |
| `40` | Shared secret could not be resolved (e.g. var not in `.env`) |
| `30` | Server-side: `PermissionError` (bad secret / non-allowlisted email / uplink-only) or `LookupError` (user not found) |
| `0` | Happy path — inner function's return value is printed |

## Rotation

Rotate the shared secret without downtime by using both old + new briefly:

1. Generate a new secret locally: `openssl rand -hex 32`.
2. Temporarily rewrite the helper to accept either the old or the new:
   ```python
   expected_old = anvil.secrets.get_secret("anvil_uplink_shared_secret")
   expected_new = anvil.secrets.get_secret("anvil_uplink_shared_secret_next")
   if shared_secret not in (expected_old, expected_new):
       raise PermissionError(...)
   ```
3. Deploy. Update `.env` on every machine to the new secret.
4. Promote: swap the secrets (`anvil_uplink_shared_secret = <new value>`), revert the helper to the single-secret form, deploy again.

## Warnings

- **Never put real customer email domains in the allowlist.** If someone exfiltrates both your uplink key and shared secret, the allowlist is the only barrier between them and your paying users.
- **Pick a domain your app's signup flow cannot accept.** If the allowlist suffix is a domain reachable via `anvil.users.signup_with_email` (or any self-signup path), an attacker who already holds the uplink key + shared secret can create their own account into the allowlist and self-elevate. Prefer a reserved or internal-only domain, and/or reject signups with the service-account suffix.
- **Don't impersonate without the allowlist.** The empty `_ALLOWED_EMAIL_SUFFIXES = ()` default rejects all calls on purpose — so a copy-pasted example never becomes a live authority.
- **Every allowlist entry must start with `@`.** The template's `assert` enforces this at import time; the `@` prevents a substring bypass like `"attacker@evil.yourco.internal"` matching a suffix `"yourco.internal"`.
- **Inner callable serialization.** `args` / `kwargs` pass through `anvil.server.call` twice (CLI -> dispatcher -> target). They must be JSON-native (or Anvil-portable). This is fine for diagnostics and admin flows; don't use it to pass arbitrary Python objects.
- **Service accounts need the same auxiliary setup as a real user.** If your callables check `users/<row>/has_role` or similar side-table lookups, make sure the service account has matching rows, or the `require_user` gate will pass but the business-logic gate will still reject.
- **Shell history retains `--as-user`.** The email itself is not a secret, but it does tell a local observer which identities are impersonable. Treat shell history on shared hosts accordingly. The shared secret stays in `.env` and is never placed on the command line.

## Data protection notes

The `uplink_audit` rows contain personal data (`impersonated_email`, `caller_ip`) and become your responsibility as data controller when you deploy the helper. Non-exhaustive checklist:

- **Retention.** Decide a retention window (e.g. 90 days) and schedule deletion. Storage-limitation expectations under GDPR Art. 5(1)(e) apply if your users are in the EU/UK/EEA.
- **Erasure.** A data subject who requests erasure over an email in `impersonated_email` should be removable. A background job can delete matching rows; audit intent is not an automatic exemption.
- **ROPA.** Include this processing in your Record of Processing Activities (GDPR Art. 30). The usual lawful basis is legitimate interest (fraud prevention / accountability) — document it before relying on it.
- **Access control.** Set the `uplink_audit` table to Forms=None, Server=Full (step 2 above). Do not expose rows to Client Uplinks or the browser.
- **Spreadsheet exports.** If you ever export `uplink_audit` to Excel/CSV, treat `error_message` as untrusted text and strip leading `=`, `+`, `-`, `@` to prevent formula injection.

This is guidance, not legal advice — consult a qualified attorney for binding opinions specific to your jurisdiction and data-subject population.
