#!/usr/bin/env bash
# Baseline gate for the test suite.
#
# The suite has a known-RED baseline recorded in CLAUDE.md: R = 32/64 passed.
# Fail when the run regresses below that baseline:
#   - pytest crashes or produces no parseable summary,
#   - any collection/execution error, or
#   - passed/total drops below 32/64.
# It succeeds (exit 0) at or above baseline, even while failures remain.
set -u

BASELINE_NUM=32
BASELINE_DEN=64

output="$(uv run pytest -q -p no:cacheprovider --tb=short 2>&1)"
pytest_status=$?
printf '%s\n' "$output" | tail -n 5

# pytest exit codes: 0 = all passed, 1 = test failures (the expected
# baseline state). Anything above 1 is an internal error, usage error or
# interrupt — the summary may be partial, so fail closed.
if [ "$pytest_status" -gt 1 ]; then
  echo "FAIL: pytest exited with status $pytest_status" >&2
  exit 1
fi

# Extract a summary counter: take the LAST match (the summary is the final
# place counters appear) and keep only digits, so the result is always a
# single integer (or empty -> defaulted to 0 below).
count() {
  printf '%s\n' "$output" | grep -oE "[0-9]+ $1" | tail -n 1 | grep -oE '^[0-9]+' || true
}
passed="$(count passed)";     passed="${passed:-0}"
failed="$(count failed)";     failed="${failed:-0}"
errors="$(count 'errors?')";  errors="${errors:-0}"
skipped="$(count skipped)";   skipped="${skipped:-0}"

total=$((passed + failed + errors + skipped))

if [ "$total" -eq 0 ]; then
  echo "FAIL: no pytest summary parsed (crash, interrupt, or empty run)" >&2
  exit 1
fi
if [ "$errors" -ne 0 ]; then
  echo "FAIL: $errors error(s); baseline requires 0" >&2
  exit 1
fi
if [ $((passed * BASELINE_DEN)) -lt $((BASELINE_NUM * total)) ]; then
  echo "FAIL: $passed/$total below baseline R (${BASELINE_NUM}/${BASELINE_DEN})" >&2
  exit 1
fi
echo "OK: $passed/$total passed >= baseline R (${BASELINE_NUM}/${BASELINE_DEN})"
