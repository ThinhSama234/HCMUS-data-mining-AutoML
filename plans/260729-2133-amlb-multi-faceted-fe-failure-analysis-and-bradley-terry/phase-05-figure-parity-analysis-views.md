---
phase: 5
title: "Figure-parity analysis views"
status: completed
priority: P2
effort: "2-3d"
dependencies: [2, 4]
---

# Phase 5: Figure-parity analysis views

## Overview

Back the report's remaining analytical figures with real E2E code so the Evaluation page
reproduces them from `repo.load()` (INV-2), instead of them being one-off PNGs. Covers the
figures that are *missing or only partially* backed today: dataset-overview charts (report
Hình 1–2), normalized-score boxplots (Hình 4), raw per-fold score boxplots (Hình 5),
score-vs-time scatter (Hình 6), and an inference-time boxplot (Hình 8). Each is a small pure
`analysis/*` function discovered via `explorer._optional_module`, rendered with graceful
degrade — same pattern as Phases 1–3.

## Requirements

- Functional:
  - **Dataset overview (Hình 1–2):** task-type composition (pie) + rows / #features per
    dataset (bar) from the **catalog** (`repo.list_datasets`) — on the Datasets page.
  - **Normalized-score boxplot (Hình 4):** per-dataset min-max normalize `score` to [0,1]
    (1 = best framework on that dataset), boxplot per framework, overall + split by `type`.
  - **Raw score boxplots (Hình 5):** distribution of per-fold `score` per (dataset ×
    framework), grouped by task type.
  - **Score-vs-time (Hình 6):** mean `score` vs mean `training_duration` (log x), one panel
    per task type, colored by framework.
  - **Inference-time boxplot (Hình 8):** `predict_duration` distribution per framework
    (log y). Reuse `pareto.py`'s median if convenient; this adds the full distribution.
- Non-functional:
  - Pure logic in `analysis/*`; FE only renders. No new heavy deps (pandas + plotly only).
  - Every section degrades gracefully when its column/module is absent (US3/US4 pattern).
  - Normalization + grouping never mix metrics across task types (FR-008), consistent with
    `rankings.py`.

## Architecture

New pure module(s) under `analysis/`, kept small and single-purpose (KISS). Group the
score-shaped views into one module to avoid over-splitting:

- `analysis/score_shapes.py` — `normalized_scores(df)`, `score_long(df)` (per-fold tidy),
  `score_vs_time(df)`, `inference_times(df)`. All read the tidy frame from `load_results` /
  `repo.load()` (columns: `framework, task, type, fold, score, training_duration,
  predict_duration`).
- Dataset-overview charts read the **catalog** directly in the view via `state`/`repo`
  (`list_datasets`) — no results needed, so they work even before Phase 4 import.

Wire-up mirrors existing code: `explorer.score_shapes_module()` via `_optional_module`;
Evaluation adds sections guarded by `if mod is None: st.info(...)`. Dataset-overview goes on
the **Datasets** page (`console/views/datasets.py`), next to the existing catalog table.

Normalization detail (Hình 4): within each `task`, `norm = (score - min) / (max - min)` over
frameworks on that task (guard max==min → 1.0). This is metric-agnostic because `score` is
already direction-normalized by `load_results`.

## Related Code Files

- Create: `analysis/score_shapes.py` — the four functions above + `main(argv)` CLI (mirror
  `pareto.py`).
- Modify: `analysis/explorer.py` — add `score_shapes_module()` via `_optional_module`.
- Modify: `console/views/evaluation.py` — add "Normalized performance", "Score distribution",
  "Score vs training time", "Inference time" sections (Plotly box/scatter), each graceful.
- Modify: `console/views/datasets.py` — add task-type pie + rows/#features bar from the catalog.
- Create: `tests/test_score_shapes.py` — synthetic df: assert normalization ∈ [0,1] with the
  per-task best = 1.0; assert score_vs_time / inference_times shapes and grouping.

## Implementation Steps

1. Implement `analysis/score_shapes.py` (normalized_scores → score_long → score_vs_time →
   inference_times); reuse `load_results` column contract; no metric mixing across `type`.
2. Add `score_shapes_module()` to `explorer.py`.
3. Add the four Evaluation sections (Plotly), each behind a graceful-degrade guard; reuse the
   already-filtered `fdf`.
4. Add dataset-overview pie + bar to `datasets.py` from `list_datasets()` (catalog only).
5. Write `tests/test_score_shapes.py`; run `pytest tests/test_score_shapes.py -q`.
6. With Phase 4 data imported, eyeball each section against the matching report figure (4/5/6/8)
   and the dataset overview against Hình 1–2.

## Success Criteria

- [x] Evaluation reproduces Hình 4 (normalized boxplot overall + by task), Hình 5 (per-fold
      score boxplots), Hình 6 (score-vs-time), Hình 8 (inference-time boxplot) from real data.
- [x] Datasets page shows task-type composition + rows/#features from the catalog (Hình 1–2).
- [x] All logic in `analysis/score_shapes.py`, unit-tested; views only render and degrade gracefully.
- [x] No metric mixing across task types; normalization matches per-dataset best = 1.0.

## Progress (2026-07-30)

Done + tested (`tests/test_score_shapes.py`, 7 cases; full suite 110 green; verified live in the
console with catalog + smoke data):
- `analysis/score_shapes.py` — `normalized_scores` (Hình 4), `score_long` (Hình 5),
  `score_vs_time` (Hình 6), `inference_times` (Hình 8); pure, metric-safe (per-task
  normalization / per-type facets), each degrades to an empty frame on missing columns/rows.
- `explorer.score_shapes_module()`; Evaluation gains 4 guarded sections; `console/views/datasets.py`
  gains a "Catalog overview" (task-type pie + rows/#features bars) from `repo.list_datasets`.
- Code-review fixes: **M1** — NULL `task_type` datasets are kept as `"unknown"` (fillna) across
  all three score helpers instead of being silently dropped from 2 of them (cross-figure
  consistency); **L1** — corrected the `metric_value` doc (raw `result_num`, not "direction-normalized").
- Verified live: score sections render (facet by task type) on smoke; Datasets overview renders
  pie + both bars on real catalog data. `inference_times` is empty on report-only data (no
  `predict_duration`) and the section degrades — as designed.

## Known trade-off

Within a task-type facet, Hình 5/6 share one metric y-axis across datasets, so very different
metric scales (e.g. regression RMSE across datasets) compress — this matches the report's own
figures (raw, per-task-type) and is a deliberate parity choice, not a defect.

## Risk Assessment

- **Risk:** module sprawl (one file per figure). **Mitigation:** one `score_shapes.py` groups
  the score-shaped views; only split if a function grows its own concern.
- **Note:** target-distribution figure (Hình 3) is a **validated non-goal** — stays static in
  the report (needs raw-file plotting via object store; not worth the E2E cost). Not built here.
- **Risk:** small/smoke data → ugly boxplots. **Mitigation:** graceful empty-state + caption
  that spread widens with the full suite (existing convention).
