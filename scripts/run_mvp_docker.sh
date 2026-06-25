#!/usr/bin/env bash
# MVP smoke via prebuilt AMLB Docker images — NO local AMLB clone / pip needed (only Docker
# or Rancher Desktop in moby mode). Each automlbenchmark/<framework> image embeds the AMLB
# app; we mount our userdir + results. Arg/mount pattern mirrors AMLB's amlb/runners/docker.py.
#
# Usage:
#   bash scripts/run_mvp_docker.sh                          # all runners (baselines + frameworks)
#   RUNNERS="flaml" bash scripts/run_mvp_docker.sh          # subset
#
# Published images are **amd64-only** and built on AMLB v2.1.3 (older than a local clone).
# On Apple Silicon they run under emulation (--platform linux/amd64) — works but slow; enable
# Rosetta in Rancher/Docker for speed. Tags are per-framework version strings (no `latest`);
# defaults below are the newest published as of 2026-06 — check hub.docker.com/u/automlbenchmark.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
USERDIR="$HERE/amlb_userdir"
OUTDIR="$HERE/results"
BENCHMARK="mvp"
CONSTRAINT="smoke"
read -ra RUNNERS <<< "${RUNNERS:-constantpredictor RandomForest flaml H2OAutoML AutoGluon}"

# newest published tag per framework (override one with e.g. TAG_flaml=...)
default_tag() {
  case "$1" in
    flaml)             echo "${TAG_flaml:-1.2.4-v2.1.3}" ;;
    H2OAutoML)         echo "${TAG_H2OAutoML:-3.40.0.4-v2.1.3}" ;;
    AutoGluon)         echo "${TAG_AutoGluon:-0.8.0-v2.1.3}" ;;
    RandomForest)      echo "${TAG_RandomForest:-1.2.2-v2.1.3}" ;;
    constantpredictor) echo "${TAG_constantpredictor:-stable}" ;;
    *)                 echo "stable" ;;
  esac
}

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker CLI not found." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "ERROR: Docker/Rancher daemon not running — start it first." >&2; exit 1; }

mkdir -p "$OUTDIR"
for fw in "${RUNNERS[@]}"; do
  img="automlbenchmark/$(echo "$fw" | tr '[:upper:]' '[:lower:]'):$(default_tag "$fw")"
  echo "=== $fw via $img ==="
  docker run --rm --platform linux/amd64 \
    -v "$USERDIR":/custom -v "$OUTDIR":/output \
    "$img" \
    "$fw" "$BENCHMARK" "$CONSTRAINT" -o /output -u /custom -s skip \
    || echo "WARN: $fw failed (arch/tag/run error) — continuing"
done
echo "Done → $OUTDIR/results.csv"
echo "Next:  streamlit run console/app.py"
