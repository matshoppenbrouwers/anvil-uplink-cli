#!/usr/bin/env bash
# Probe: H8 (serialize-inside-uplink) + H9 (run.py exposes `server` in namespace)
# + H15 (query --limit 0 returns empty) + H16 (out-of-scope features genuinely absent)
set -u
LOG=_verification/2026-04-21-anvil-uplink-cli-integration.log
PASS=0; FAIL=0

check() {  # $1 label, $2 "should"/"shouldnot", $3 pattern, $4 file
  local label="$1" mode="$2" pat="$3" file="$4"
  if grep -qE "$pat" "$file"; then found=1; else found=0; fi
  case "$mode" in
    should)
      if [ "$found" = "1" ]; then echo "PASS: $label" | tee -a "$LOG"; PASS=$((PASS+1))
      else echo "FAIL: $label (expected /$pat/ in $file)" | tee -a "$LOG"; FAIL=$((FAIL+1)); fi ;;
    shouldnot)
      if [ "$found" = "0" ]; then echo "PASS: $label" | tee -a "$LOG"; PASS=$((PASS+1))
      else echo "FAIL: $label (unexpected /$pat/ in $file)" | tee -a "$LOG"; FAIL=$((FAIL+1)); fi ;;
  esac
}

echo "=== Defect regression + out-of-scope probe @ $(date) ===" | tee -a "$LOG"

# H8: serialize-inside-uplink. The to_jsonable call must appear BEFORE the uplink
# context exits. We look for the pattern "with uplink" ... "to_jsonable" before a
# de-indent. Simpler: assert no `to_jsonable` appears after `with uplink(`...`):` closes.
# Instead, use awk to check indentation relative to `with uplink`.
for f in src/anvil_uplink_cli/commands/query.py src/anvil_uplink_cli/commands/row.py src/anvil_uplink_cli/commands/call.py; do
  result=$(awk '
    /with uplink\(/ { inside=1; ind=match($0,/[^ ]/); next }
    inside && /to_jsonable\(/ { print "inside"; exit }
    inside && /^[^ ]/ { inside=0 }
    inside && match($0,/[^ ]/) <= ind && !/^$/ { inside=0 }
  ' "$f")
  if [ "$result" = "inside" ]; then
    echo "PASS: H8 to_jsonable inside with-uplink in $f" | tee -a "$LOG"; PASS=$((PASS+1))
  else
    echo "FAIL: H8 to_jsonable outside with-uplink in $f" | tee -a "$LOG"; FAIL=$((FAIL+1))
  fi
done

# H9: run.py exposes `server` key in namespace
check "H9 run.py namespace has 'server' key" should '"server": *anvil\.server' src/anvil_uplink_cli/commands/run.py

# H15: query._collect_rows respects limit=0 (break on i >= limit before append)
check "H15 query._collect_rows has i >= limit guard" should 'i >= limit' src/anvil_uplink_cli/commands/query.py

# H16: out-of-scope features genuinely absent
check "H16.daemon mode not built" shouldnot 'daemon|DaemonMode|long.lived.connection' src/anvil_uplink_cli/cli.py
check "H16.MCP server not built" shouldnot 'mcp[._ ]server|McpServer' src/anvil_uplink_cli/cli.py
# Negative scan across whole package
PKG=src/anvil_uplink_cli
if grep -rE 'class DaemonMode|class MCPServer|def start_daemon' "$PKG" 2>/dev/null; then
  echo "FAIL: H16 found out-of-scope daemon/MCP class" | tee -a "$LOG"; FAIL=$((FAIL+1))
else
  echo "PASS: H16 no daemon/MCP class in package" | tee -a "$LOG"; PASS=$((PASS+1))
fi

echo "=== RESULTS: $PASS passed, $FAIL failed ===" | tee -a "$LOG"
exit $FAIL
