#!/usr/bin/env bash
# Probe: Typer surface-area checks. Covers H1, H2, H10, H11, H12, H13, H14.
# Runs the CLI end-to-end (no network) and asserts stdout + exit codes.
set -u
CLI=/tmp/test-venv/bin/anvil-bridge
LOG=_verification/2026-04-21-anvil-uplink-cli-integration.log
PASS=0; FAIL=0

assert_contains() {  # $1 haystack, $2 needle, $3 label
  if grep -q -- "$2" <<<"$1"; then echo "PASS: $3" | tee -a "$LOG"; PASS=$((PASS+1))
  else echo "FAIL: $3 (needle: $2 not in: $1)" | tee -a "$LOG"; FAIL=$((FAIL+1)); fi
}
assert_exit() {  # $1 actual, $2 expected, $3 label
  if [ "$1" = "$2" ]; then echo "PASS: $3 (exit=$1)" | tee -a "$LOG"; PASS=$((PASS+1))
  else echo "FAIL: $3 (exit=$1, expected=$2)" | tee -a "$LOG"; FAIL=$((FAIL+1)); fi
}

echo "=== CLI surface probe @ $(date) ===" | tee "$LOG"

# H1: help lists all 8 commands
OUT=$("$CLI" --help 2>&1); RC=$?
assert_exit "$RC" "0" "H1.0 --help exits 0"
for c in init doctor call query tables row run repl; do
  assert_contains "$OUT" "$c" "H1.$c command listed in --help"
done

# H12: -h short flag
OUT=$("$CLI" -h 2>&1); RC=$?
assert_exit "$RC" "0" "H12 -h short flag accepted"

# H2: --version
OUT=$("$CLI" --version 2>&1); RC=$?
assert_exit "$RC" "0" "H2.0 --version exits 0"
assert_contains "$OUT" "anvil-bridge 0.1.0" "H2.1 --version prints expected string"

# H14: unknown profile → ConfigError / exit 41
export XDG_CONFIG_HOME=/tmp/anvil-verify-empty
mkdir -p "$XDG_CONFIG_HOME/anvil-bridge"
echo "" > "$XDG_CONFIG_HOME/anvil-bridge/config.toml"
OUT=$("$CLI" doctor --profile does-not-exist 2>&1); RC=$?
assert_exit "$RC" "41" "H14 unknown profile exits 41 (ConfigError)"
assert_contains "$OUT" "not found" "H14.1 unknown profile reports 'not found'"

# H11: ValueError → EXIT_USAGE=2 for malformed --kwarg (before any network attempt)
# Set up a valid profile with an env-var key (won't be used because parse fails first)
cat > "$XDG_CONFIG_HOME/anvil-bridge/config.toml" <<EOF
[profiles.t]
url = "wss://anvil.works/uplink"
key_ref = "env:NEVER_READ"
default = true
EOF
export NEVER_READ="placeholder"
OUT=$("$CLI" call some_fn --kwarg 'no_equals_sign' 2>&1); RC=$?
assert_exit "$RC" "2" "H11.0 malformed --kwarg exits 2 (EXIT_USAGE)"
assert_contains "$OUT" "usage error" "H11.1 malformed --kwarg prefixes 'usage error'"

# H10: init --non-interactive without --profile fails when profiles exist
OUT=$("$CLI" init --non-interactive --key-from-env SOMEVAR 2>&1); RC=$?
# Typer exit code for BadParameter is 2
assert_exit "$RC" "2" "H10 init --non-interactive without --profile rejected when profiles exist"

# H13: run executes script and propagates SystemExit(5)
cat > /tmp/anvil-exit5.py <<'EOF'
import sys
sys.exit(5)
EOF
# This would try to connect; we can't mock in bash. But the ConfigError path for a
# missing key should trigger before connect. Use a profile with a missing env var.
cat > "$XDG_CONFIG_HOME/anvil-bridge/config.toml" <<EOF
[profiles.broken]
url = "wss://anvil.works/uplink"
key_ref = "env:DEFINITELY_UNSET_XYZ"
default = true
EOF
unset DEFINITELY_UNSET_XYZ
OUT=$("$CLI" run /tmp/anvil-exit5.py 2>&1); RC=$?
# Expect auth error (40), not a script-level SystemExit(5), because key resolution fails first.
# H13 behavior (sys.exit(5) propagates) cannot be verified without a live connection — deferred.
assert_exit "$RC" "40" "H13-proxy auth error surfaces before exec (live-exec path deferred)"

echo "=== RESULTS: $PASS passed, $FAIL failed ===" | tee -a "$LOG"
exit $FAIL
