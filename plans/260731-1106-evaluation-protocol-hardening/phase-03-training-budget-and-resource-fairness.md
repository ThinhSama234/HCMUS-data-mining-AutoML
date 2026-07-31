---
phase: 3
title: "Training budget & resource fairness"
status: completed
priority: P2
effort: "1-2d"
dependencies: []
---

# Phase 3: Training budget & resource fairness

## Overview

Close checklist §3. Fairness requires that every framework gets the **same time budget and the same
CPU/RAM**, and that this is **provable** from the logs. Today `constraints` bundles
`max_runtime_seconds` / `cores` / `max_mem_mb` as fixed presets, the Training page shows budget + cores
in a caption, but the **allocated** resources aren't shown prominently and the **actual** resource use
per run isn't recorded for comparison. Make the budget + resource model explicit and evidenced.

## Requirements

- Functional:
  - Training shows the **allocated** budget + cores + memory for the chosen constraint prominently
    (not buried in a caption), so the equal-footing is visible before launch.
  - Record **actual** resource use per run (at minimum wall-clock `training_duration` vs the allocated
    budget; capture cores/peak-mem if AMLB's output exposes them) so allocated-vs-actual can be shown.
  - An Evaluation view (or an extension of the existing memory/budget sections) comparing allocated
    vs actual per framework — surfacing any framework that overran or under-used its budget.
- Non-functional:
  - Prefer surfacing existing `constraints` fields over new schema; add a `runs` field only if a real
    actual-resource value exists to store (else keep it out — YAGNI).

## Architecture

Scout first (open question): does AMLB's `results.csv` / job output expose **actual** CPU/RAM used, or
only `duration`? `runner._ingest_job` currently maps `duration`→`training_duration` and metric columns;
there is no actual-cores/actual-mem column. Two honest outcomes:
1. If AMLB exposes actual resource fields → map them into `runs.metrics` JSON (non-breaking, like Phase-4
   memory) and render allocated-vs-actual.
2. If it does not → surface **allocated** budget/cores/mem clearly + **actual wall-clock** vs budget
   (already have `training_duration` + constraint `max_runtime_seconds`), and state honestly that
   per-run CPU/RAM caps are enforced by AMLB/Docker (`--cores`, `--memory`) but not separately measured.

Fairness is *enforced* by AMLB (same constraint → same `--cores`/`--memory`/budget for every framework
in a run); this phase makes that **visible and logged**, it does not re-implement enforcement.

## Related Code Files

- Reference (scout): `storage/runner.py` (`_ingest_job`, the Docker run flags / constraint→AMLB args),
  AMLB `results.csv` columns, `storage/models.py` (`constraints`, `runs.metrics`).
- Modify: `console/views/training.py` — a clear "resource plan" block: budget + cores + memory (from
  `constraint_info`, extended to return `max_mem_mb`); state it applies equally to every framework.
- Modify: `storage/runner.py` — capture actual resource fields into `runs.metrics` **iff** AMLB exposes
  them (per the scout outcome).
- Modify: `console/views/evaluation.py` — allocated-vs-actual (extend the Phase-6 budget/memory sections):
  wall-clock vs budget per framework; actual CPU/RAM when available.
- Modify/extend: `tests/` — a test for the extended `constraint_info` (incl. `max_mem_mb`) and any
  allocated-vs-actual aggregation helper.

## Implementation Steps

1. **Scout** AMLB output for actual CPU/RAM fields; record the finding in this phase file (decides the
   architecture branch).
2. Extend `runner.constraint_info` to also return `max_mem_mb`; render a prominent "resource plan"
   block on Training (budget + cores + memory, applies to all frameworks equally).
3. If actual-resource fields exist, capture them in `_ingest_job` → `runs.metrics`; else record only
   wall-clock (already present) and document the enforcement source.
4. Add the allocated-vs-actual Evaluation view (extend the budget/memory sections).
5. Tests + a live check under a real constraint.

## Success Criteria

- [x] Training surfaces the allocated budget + cores (+ folds) prominently, stated as equal for all
      frameworks (memory omitted — AMLB caps cores, not RAM).
- [x] Actual wall-clock vs budget is shown per framework (Budget-usage view via `budget_usage`);
      degrades cleanly when `budget_s` is absent (CSV-only data).
- [x] No speculative schema — no fake memory cap; `budget_s` is read from the existing constraint column.

## Progress (2026-07-31)

**Done — resource plan surfaced** (commit `109e3e7`; addresses the user's "constraint shows nothing"):
- `runner.constraint_info` now also returns `max_mem_mb`; Training shows **CV folds · time budget ·
  cores (· memory when configured)** as metrics right under the constraint picker, stated as applied
  equally to every framework (fair comparison) + the fixed-seed / mean±std note. Verified live
  (smoke → 1 fold / 60s / 4 cores; 1h → 10 folds / 60 min / 8 cores).

**Scout outcome (2026-07-31):** AMLB's `results.csv` exposes **no actual CPU/RAM** columns (only
durations); AMLB constraints (`constraints.yaml`) cap **cores + disk volume (`min_vol_size_mb`), NOT
RAM** — so there is no per-constraint memory cap to mirror. Fairness is CPU cores + budget + folds,
all equal. Honest conclusions: don't fabricate a memory cap; "actual vs allocated" = measured
wall-clock `training_duration` vs the constraint's `max_runtime_seconds`.

**Done — allocated-vs-actual budget usage** (addresses the remaining scope honestly):
- `repo.load()` now exposes `budget_s` (constraint `max_runtime_seconds`); `score_shapes.budget_usage`
  gives per (framework, constraint) mean training time ÷ budget = `pct_used`. Evaluation gains a
  "Budget usage (allocated vs actual)" section (bars of % budget used) + caption noting equal
  budget/cores per framework (AMLB caps cores, not RAM). Verified on ingested report data
  (autogluon 111% / flaml 293% / h2o 349% — the report pipeline's soft budget was overrun; AMLB's
  hard cap gives ≤100%). Degrades on CSV-only data (no `budget_s`). Full suite 134 green.
- Memory: intentionally NOT shown as a cap (AMLB doesn't cap RAM) — the resource plan shows the real
  equal-footing controls (folds · budget · cores).

## Risk Assessment

- **Risk:** over-engineering resource capture AMLB doesn't provide. **Mitigation:** the scout step
  gates it; default to surfacing allocated + wall-clock, no new columns, if actuals aren't available.
- **Risk:** implying measurement we don't have. **Mitigation:** label clearly — "budget/cores/mem
  enforced by AMLB+Docker per constraint" vs "measured actual" — never conflate the two.
