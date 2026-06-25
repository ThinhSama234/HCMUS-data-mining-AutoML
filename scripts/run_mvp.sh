#!/usr/bin/env bash
# MVP smoke run: 3 small datasets, 1 fold, short budget — proves User Story 1 end-to-end.
# One identical protocol per runner; AMLB records failures so one bad runner won't abort.
#
# Usage:
#   bash scripts/run_mvp.sh                 # local runners (work on macOS): baselines + flaml
#   WITH_DOCKER=1 bash scripts/run_mvp.sh   # also H2O + AutoGluon via Docker (Linux images)
#   AMLB_ROOT=/path/to/automlbenchmark bash scripts/run_mvp.sh   # custom AMLB clone location
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
AMLB_ROOT="${AMLB_ROOT:-$(dirname "$HERE")/automlbenchmark}"     # default: sibling clone
AMLB="${AMLB:-python $AMLB_ROOT/runbenchmark.py}"
USERDIR="$HERE/amlb_userdir"
OUTDIR="$HERE/results"
BENCHMARK="mvp"
CONSTRAINT="smoke"

LOCAL_RUNNERS=(constantpredictor RandomForest flaml)
DOCKER_RUNNERS=(H2OAutoML AutoGluon)

if [ ! -f "$AMLB_ROOT/runbenchmark.py" ]; then
  echo "ERROR: AMLB not found at $AMLB_ROOT (clone it first — see README Setup)." >&2
  exit 1
fi

run() {  # $1 = mode, rest = runners
  local mode="$1"; shift
  for fw in "$@"; do
    echo "=== $fw · $BENCHMARK/$CONSTRAINT · $mode ==="
    $AMLB "$fw" "$BENCHMARK" "$CONSTRAINT" -m "$mode" -u "$USERDIR" -o "$OUTDIR" \
      || echo "WARN: $fw exited non-zero — continuing (AMLB records the failure)"
  done
}

mkdir -p "$OUTDIR"
run local "${LOCAL_RUNNERS[@]}"
[ "${WITH_DOCKER:-0}" = "1" ] && run docker "${DOCKER_RUNNERS[@]}"

echo "Done → $OUTDIR/results.csv"
echo "Next:  streamlit run console/app.py    (or: python -m analysis.rankings $OUTDIR/results.csv)"
