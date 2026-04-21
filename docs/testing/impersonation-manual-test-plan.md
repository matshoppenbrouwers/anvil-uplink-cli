# `--as-user` Impersonation Manual Test Plan

**Feature:** `anvil-bridge call --as-user <email>` (v0.2.0)
**Server-side template:** see `docs/impersonation.md` (hardened in v0.2.1).
**Branch (at time of writing):** `chore/v0.2.2-polish`
**Tester:** _______________  **Date:** ____-__-__

---

## How to use this plan

1. Stand up a disposable Anvil app (or reuse your staging app). Paste the helper template from `docs/impersonation.md` into `server_code/uplink_helpers.py`. Set `_ALLOWED_EMAIL_SUFFIXES` to a domain no real user account uses (e.g. `("@ops-test.internal",)`).
2. Create the `uplink_audit` data table per the doc's app-setup step.
3. Generate a shared secret: `openssl rand -hex 32`. Store it in the app's `anvil.secrets` under `anvil_uplink_shared_secret`, and in your local `.env` as `ANVIL_UPLINK_SHARED_SECRET`.
4. Create a `users` row with an email ending in the allowlist suffix (e.g. `svc@ops-test.internal`). Populate any role/team rows your `require_user` callables check.
5. Add `impersonate_secret_ref = "dotenv:ANVIL_UPLINK_SHARED_SECRET"` to the relevant profile in `~/.config/anvil-bridge/config.toml`.
6. Deploy the app. Confirm `anvil-bridge doctor --profile <name>` reports a Server Uplink.
7. Work through each test. Mark each case `[PASS]`, `[FAIL]`, or `[SKIP]` with notes.

Placeholder substitutions used below: `<APP>` = your test app profile name; `<SVC>` = the allowlisted service-account email; `<FN>` = a `@anvil.server.callable(require_user=True)` function in the app that returns something easy to verify (e.g. `anvil.users.get_user()['email']`).

---

## 1. Happy path

### 1.1 Basic invocation
- [ ] Run `anvil-bridge call <FN> --as-user <SVC> --profile <APP>`.

**Expected:** exit code `0`; stdout is the return value of `<FN>` (e.g. `<SVC>` if the function echoes the logged-in user's email).

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 1.2 Short flag `-u`
- [ ] Run the same call with `-u <SVC>` instead of `--as-user <SVC>`.

**Expected:** exit code `0`; identical behavior to 1.1.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 1.3 `--json` output
- [ ] Run `anvil-bridge call <FN> --as-user <SVC> --profile <APP> --json`.

**Expected:** exit code `0`; stdout is valid JSON (use `jq .` to verify).

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 1.4 Args and kwargs forward through the dispatcher
- [ ] Pick a callable that accepts positional + keyword args. Invoke:
  `anvil-bridge call <FN_WITH_ARGS> --as-user <SVC> --profile <APP> 42 --kwarg flag=true`

**Expected:** exit code `0`; server observes the positional and keyword args unchanged.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 1.5 Audit row (happy path)
- [ ] After 1.1 runs cleanly, inspect `uplink_audit` in the Anvil Editor.

**Expected:** one row with `result_status="ok"`, `impersonated_email=<SVC>`, `fn_name=<FN>`, and an `error_message` that is empty.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

---

## 2. Failure modes

### 2.1 Profile has no `impersonate_secret_ref`
- [ ] Temporarily remove (or rename) `impersonate_secret_ref` from the profile.
- [ ] Run `anvil-bridge call <FN> --as-user <SVC> --profile <APP>`.

**Expected:** exit code `42` (`EXIT_IMPERSONATION`); stderr contains the phrase `no impersonate_secret_ref`.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 2.2 `.env` variable missing
- [ ] Restore the `impersonate_secret_ref` but remove `ANVIL_UPLINK_SHARED_SECRET` from the `.env` (or point the ref at a non-existent var).
- [ ] Run the call.

**Expected:** exit code `40` (`EXIT_AUTH`); stderr explains the var was not found.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 2.3 Wrong shared secret
- [ ] Set `ANVIL_UPLINK_SHARED_SECRET` in the `.env` to a bogus value (different from what's in the app's secrets).
- [ ] Run the call.

**Expected:** exit code `30` (`EXIT_SERVER_RAISED`); stderr contains `invalid shared secret`.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 2.4 Non-allowlisted email
- [ ] Restore the correct shared secret.
- [ ] Run `anvil-bridge call <FN> --as-user someone@external.com --profile <APP>`.

**Expected:** exit code `30`; stderr contains `not in impersonable allowlist`.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 2.5 Email case-insensitivity (v0.2.1 template)
- [ ] Run with an uppercase variant of `<SVC>` (e.g. `SVC@OPS-TEST.INTERNAL`).

**Expected:** passes the allowlist check (template lower-cases both sides); `users.get(email=...)` may or may not find the row depending on how you registered it — either `exit 0` (if the users row matches) or `exit 30` with `LookupError: user ... not found`. What should NOT happen: rejection at the allowlist step.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 2.6 Email not in `users` table
- [ ] Run `anvil-bridge call <FN> --as-user typo@ops-test.internal --profile <APP>` (allowlisted suffix, but no matching user row).

**Expected:** exit code `30`; stderr contains `user ... not found`.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 2.7 Audit row (failure path)
- [ ] After any of 2.3–2.6 runs, inspect `uplink_audit`.

**Expected:** a row with `result_status="error"` and an `error_message` starting with the exception class name (e.g. `PermissionError(...)` — note: v0.2.1 template uses `repr(exc)`, older templates used `f"{type(exc).__name__}: {exc}"`).

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

---

## 3. Template hardening (v0.2.1)

### 3.1 Allowlist assertion fires at import time
- [ ] Temporarily edit `uplink_helpers.py` on the server and change `_ALLOWED_EMAIL_SUFFIXES` to `("ops-test.internal",)` (no leading `@`).
- [ ] Push / redeploy.

**Expected:** Anvil's server import fails with `AssertionError: _ALLOWED_EMAIL_SUFFIXES entries must start with '@'`. Any `--as-user` call while in this state either (a) cannot be handled (server-side import failure) or (b) returns a non-200 from the dispatcher — the point is the developer sees the mistake immediately.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 3.2 Restore the allowlist
- [ ] Revert to `_ALLOWED_EMAIL_SUFFIXES = ("@ops-test.internal",)` and redeploy.
- [ ] Repeat 1.1 to confirm clean operation.

**Expected:** 1.1 passes again.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 3.3 Constant-time secret compare (v0.2.1+)
- [ ] No behavioral test — this is code inspection. Confirm the deployed template uses `hmac.compare_digest(shared_secret, expected)` rather than `!=`.

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

---

## 4. Custom dispatcher name

### 4.1 Rename `_uplink_run_as`
- [ ] In the server template, rename `_uplink_run_as` to `_my_shim` (and the `@anvil.server.callable` decoration still applies).
- [ ] Add `impersonate_callable = "_my_shim"` to the profile in `config.toml`.
- [ ] Redeploy.
- [ ] Run `anvil-bridge call <FN> --as-user <SVC> --profile <APP>`.

**Expected:** exit code `0`; server `_my_shim` is invoked (check server logs / audit row).

**Result:** `[ ]` PASS / FAIL
**Notes:** _______________

### 4.2 Revert the rename
- [ ] Restore the dispatcher name to `_uplink_run_as` and remove `impersonate_callable` from the profile. Redeploy.

---

## Debugging quick reference

| Symptom | Likely cause |
|---|---|
| `exit 42: no impersonate_secret_ref` | Profile is missing the TOML entry — re-check `config.toml`. |
| `exit 40: env var ... is not set` | `.env` entry missing or misnamed. `anvil-bridge doctor --profile <APP>` also surfaces this. |
| `exit 30: invalid shared secret` | `.env` value ≠ `anvil.secrets` value. Remember the rotation flow requires updating BOTH. |
| `exit 30: not in impersonable allowlist` | Email suffix doesn't match (case-insensitive in v0.2.1+). |
| `exit 30: user ... not found` | `users` table has no row for that email. |
| `AssertionError` on server startup | Allowlist entries are missing the leading `@` (v0.2.1+ template guard). |
| Silent hang | Check Anvil's Uplink panel for trusted-Server-Uplink status and verify the key. |

Useful commands:
- `anvil-bridge doctor --profile <APP>` — confirms key + connectivity, reports Server vs Client Uplink.
- `cat .env | grep -i shared` — confirms the local env-var name matches the profile's `impersonate_secret_ref`.

---

## Verdict

| Area | Tests | Pass | Fail | Skip |
|------|------:|-----:|-----:|-----:|
| 1. Happy path | 5 | | | |
| 2. Failure modes | 7 | | | |
| 3. Template hardening (v0.2.1) | 3 | | | |
| 4. Custom dispatcher | 2 | | | |
| **Total** | **17** | | | |

**Overall verdict:** `[ ]` READY FOR RELEASE / NEEDS FIXES

**Blocking issues:**
1. _______________

**Non-blocking issues:**
1. _______________

**Tester sign-off:** _______________  **Date:** ____-__-__
