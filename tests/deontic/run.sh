#!/bin/sh
# Deontic-core golden suite. A file passes iff it exits 0 and prints no failures.
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
PETTA_DIR="${PETTA_DIR:-/home/user/Dev/PeTTa}"
SWIPL_BIN="${SWIPL_BIN:-/home/user/Dev/swipl-9.3.33/build-petta/src/swipl}"
[ -x "$SWIPL_BIN" ] || SWIPL_BIN=swipl
FAIL=0; PASS=0
for f in "$SCRIPT_DIR"/test_*.metta; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  out=$(timeout -k 5 "${TEST_TIMEOUT:-200}" "$SWIPL_BIN" --stack_limit=8g -q \
        -s "$PETTA_DIR/src/main.pl" -- "$f" --silent </dev/null 2>&1)
  code=$?
  ok=$(printf '%s\n' "$out" | grep -c '✅')
  bad=$(printf '%s\n' "$out" | grep -c '❌')
  if [ "$code" -eq 0 ] && [ "$bad" -eq 0 ]; then
    echo "PASS  $name  ($ok checks)"; PASS=$((PASS + 1))
  else
    echo "FAIL  $name  ($ok ok, $bad failed, exit $code)"
    printf '%s\n' "$out" | grep -E '❌|Error|ERROR' | head -5; FAIL=$((FAIL + 1))
  fi
done
echo "----"; echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && echo "ALL DEONTIC-CORE TESTS PASSED"
exit $FAIL
