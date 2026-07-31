---
phase: 2
title: "k-fold CV mean±std + split config"
status: completed
priority: P2
effort: "1-1.5d"
dependencies: []
---

# Phase 2: k-fold CV mean±std + split config

## Overview

Close checklist §1. The AMLB runner **already does k-fold CV** — `constraints.folds` (1 for `smoke`,
**10** for `1h`/`4h`) and AMLB emits one `runs` row per fold. The gap is *surfacing* it: report
per-(dataset×framework) **mean ± std over folds**, and make the fold/split protocol explicit on the
Training page so the reader knows it isn't a single split.

## Requirements

- Functional:
  - Evaluation shows **mean ± std** over completed folds per (dataset × framework) — extend the
    per-task table + add ±std to the mean charts (pairs with Phase 1's error bars).
  - A "folds" signal in the KPI row / captions (how many folds each result averages).
  - Training makes the protocol explicit: the chosen constraint's fold count, and a one-line note that
    AMLB uses **stratified** CV for classification with a fixed seed (documented, AMLB-internal).
- Non-functional:
  - Reuse `rankings.per_task_scores` (already returns `score_mean` / `score_std` / `folds_completed`);
    do not recompute. FE only renders.

## Architecture

`rankings.per_task_scores(df)` already aggregates `score_mean`, `score_std`, `folds_completed` over
`runs.fold`. So this phase is mostly presentation: format `mean ± std` in the per-task view, add
`error_y=std` to the mean bar charts, and add a "median folds" KPI. On single-fold data (`smoke`,
folds=1) std is 0/NaN → show mean only, with a caption that std fills in under a multi-fold constraint.
Stratification is an AMLB default (its `runbenchmark.py` stratifies classification folds) — surface it
as a caption on Training, not new code.

## Related Code Files

- Modify: `analysis/rankings.py` — confirm/extend `per_task_scores` returns std usably; optionally a
  small `mean_std_table(df)` helper that formats `"{mean:.4f} ± {std:.4f}"` per (dataset, framework).
- Modify: `console/views/evaluation.py` — per-task table shows `mean ± std`; add `error_y` (std) to the
  leaderboard / normalized / score charts; a "Folds" KPI or caption.
- Modify: `console/views/training.py` — caption stating fold count (from `constraint_info`) + the
  stratified-CV + fixed-seed protocol note.
- Modify/extend: `tests/test_rankings.py` — assert `score_std` / `folds_completed` over a multi-fold
  fixture; a helper-format test if `mean_std_table` is added.

## Implementation Steps

1. Verify `per_task_scores` std/folds columns on a multi-fold fixture; add a `mean_std_table` formatter
   if the view needs it.
2. Update the Evaluation per-task table to show `mean ± std`; add std error bars to the mean charts.
3. Add a "folds" KPI/caption; caption that std needs a multi-fold constraint when folds=1.
4. Add the Training protocol caption (fold count + stratified + seed).
5. Tests for the std/folds aggregation; run `pytest tests/test_rankings.py -q`. Verify live under the
   `1h` constraint (or a multi-fold fixture) that ± std renders.

## Success Criteria

- [x] Per-(dataset×framework) results display **mean ± std over K folds** (Per-task table via
      `rankings.mean_std_table`); a "Folds / result" KPI shows how many folds each score averages.
      (Distribution/spread is also shown by the existing per-fold boxplots; dedicated error-bar charts
      are moot on the current single-fold data and were not added — YAGNI.)
- [x] Training shows the fold count (k-fold vs single split) + fixed per-fold seed; stratification
      hedged honestly to OpenML classification splits (AMLB only guarantees it there).
- [x] Single-fold data degrades to mean-only; no recompute of stats in the view (reuses `per_task_scores`).

## Progress (2026-07-31)

Done + tested (`tests/test_rankings.py`, 6 cases incl. 3 new; full suite 132 green; AppTest renders
evaluation.py + training.py no-exception):
- `analysis/rankings.mean_std_table(df)` — per (dataset×framework) `mean ± std` over folds (mean-only
  when std is NaN), reusing `per_task_scores` (INV-2, no recompute).
- Evaluation: "Folds / result" KPI (median folds averaged) + the "Per-task scores (mean ± std)" table.
- Training: caption states k-fold-vs-single-split, fixed per-fold seed, and mean±std reporting — all
  verified against AMLB (`resources.seed` fixed per fold; stratification only guaranteed for OpenML tasks).
- Code-review: **DONE**, no Critical/Important; fixed the one Minor (caption no longer says "mean ± std
  over folds" on a single split).

## Risk Assessment

- **Risk:** current committed data is single-fold (`smoke`) so std is empty. **Mitigation:** graceful
  mean-only + caption; real ± std appears under `1h`/`4h` or after Phase 5's runs.
- **Risk:** claiming "stratified" without proof. **Mitigation:** verify AMLB's fold strategy from its
  `runbenchmark.py`/docs before asserting it in the caption; if unverifiable, word it as "AMLB default CV".
