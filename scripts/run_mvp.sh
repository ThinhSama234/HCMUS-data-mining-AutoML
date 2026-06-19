#!/usr/bin/env bash
# MVP smoke run: 3 small datasets, 1 fold, ~10-min budget, LOCAL mode (CPU).
# Proves User Story 1 end-to-end. Failures are captured by AMLB, so one runner
# failing does NOT abort the loop.
#
# Prereq: AMLB installed. Set AMLB to how you invoke it, e.g.:
#   AMLB="python ../automlbenchmark/runbenchmark.py" bash scripts/run_mvp.sh
set -uo pipefail

AMLB="${AMLB:-python runbenchmark.py}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
USERDIR="$HERE/amlb_userdir"
OUTDIR="$HERE/results"
BENCHMARK="mvp"
CONSTRAINT="smoke"
MODE="${MODE:-local}"

RUNNERS=(constantpredictor RandomForest TunedRandomForest H2OAutoML flaml AutoGluon)

mkdir -p "$OUTDIR"
for fw in "${RUNNERS[@]}"; do
  echo "=== $fw on $BENCHMARK/$CONSTRAINT ($MODE) ==="
  $AMLB "$fw" "$BENCHMARK" "$CONSTRAINT" -m "$MODE" -u "$USERDIR" -o "$OUTDIR" \
    || echo "WARN: $fw exited non-zero — continuing (AMLB records the failure)"
done
echo "Done. See $OUTDIR for results.csv, then: python -m analysis.rankings $OUTDIR/<run>/results.csv"
