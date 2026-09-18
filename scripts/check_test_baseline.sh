#!/usr/bin/env bash
# Baseline gate for the test suite.
#
# The suite has a known-RED baseline recorded in CLAUDE.md: R = 32/64 passed.
# This gate fails only when the suite regresses below that baseline:
#   - any collection/execution error, or
#   - fewer than 32 passing tests.
# It succeeds (exit 0) at or above baseline, even while failures remain.
set -u

BASELINE_PASSED=32

output="$(uv run pytest -q -p no:cacheprovider --tb=short 2>&1 || true)"
echo "$output" | tail -n 5

passed="$(echo "$output" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || true)"
errors="$(echo "$output" | grep -oE '[0-9]+ errors?' | grep -oE '[0-9]+' || true)"
passed="${passed:-0}"
errors="${errors:-0}"

if [ "$errors" -ne 0 ]; then
  echo "FAIL: suite produced $errors error(s); baseline requires 0" >&2
  exit 1
fi
if [ "$passed" -lt "$BASELINE_PASSED" ]; then
  echo "FAIL: $passed passed < baseline R (${BASELINE_PASSED}/64)" >&2
  exit 1
fi
echo "OK: $passed passed >= baseline R (${BASELINE_PASSED}/64)"
