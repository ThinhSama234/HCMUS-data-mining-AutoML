---
phase: 6
title: "Budget dimension and failure enrichment"
status: completed
priority: P3
effort: "0.5-1d"
dependencies: [2, 4]
---

# Phase 6: Budget dimension and failure enrichment

## Overview

Back the report's perf-by-budget (Hình 7), **memory (Hình 9)**, and enrich Phase 1's failure
section with by-size/by-budget panels (Hình 10). All three are cheap once Phase 4 ingests
`reports/*.json`: that schema carries `time_budget` **and `peak_memory_mb`**, so memory is
readable from `runs.metrics` JSON — no results-schema migration required (a first-class
`peak_memory_mb` column is an optional call if querying by memory is wanted).

## Requirements

- Functional:
  - **Perf-by-budget (Hình 7):** normalized performance across budgets (e.g. 60s vs 300s) per
    framework — grouped bar + per-framework trajectory. Reads `constraint` +
    `constraints.max_runtime_seconds`.
  - **Memory (Hình 9):** per-(dataset × framework) heatmap + per-framework mean, reading
    `peak_memory_mb` from `runs.metrics` JSON (Phase 4 stashes `resource_usage` there).
  - **Failure enrichment (Hình 10):** extend the existing Phase 1 failure section with the
    by-size breakdown (uses Phase 2 `size_tier`) and the by-budget panel on real data.
- Non-functional:
  - Pure logic in `analysis/*`; views only render + degrade gracefully.
  - Reuse Phase 5's `normalized_scores`; do not recompute normalization.
  - Degrades to a single bar + note when only one budget is present.

## Architecture

Budget already flows through `repo.load()` as `constraint`. Add `budget_performance(df)` — the
cleanest home is to **extend `analysis/score_shapes.py`** (Phase 5) rather than a new module,
reusing `normalized_scores`. Failure enrichment needs no new module: `analysis/failures.py`
already returns per-`constraint` counts; add the by-`size_tier` grouping by joining Phase 2
characteristics (`with_characteristics`), then the Evaluation section renders the extra panels
behind column-presence guards.

## Related Code Files

- Modify: `analysis/score_shapes.py` — add `budget_performance(df)` (per framework × budget,
  normalized), or a tiny `analysis/by_budget.py` if it reads cleaner.
- Modify: `analysis/failures.py` — add `by_size(df, meta)` (failure counts per `size_tier`)
  reusing `by_characteristics.with_characteristics`.
- Modify: `console/views/evaluation.py` — add "Performance by budget" section; extend the
  "Failure analysis" section with by-size + by-budget panels (guarded by column presence).
- Modify/extend: `tests/test_score_shapes.py` (+ `tests/test_failures.py`) — synthetic
  multi-budget df: assert budget trajectory shape; assert by-size failure aggregation.

## Implementation Steps

1. Implement `budget_performance(df)` on top of Phase 5 `normalized_scores`.
2. Add the "Performance by budget" Evaluation section (grouped bar + trajectory), graceful when
   only one budget exists.
3. Add `failures.by_size(df, meta)` and render the by-size bubble/bar + by-budget panel in the
   existing failure section, behind `size_tier`/`constraint` presence guards.
4. Extend tests; run `pytest tests/test_score_shapes.py tests/test_failures.py -q`.
5. Verify Hình 7 and the enriched Hình 10 against the report on real multi-budget data.

## Success Criteria

- [x] Evaluation shows performance-by-budget (Hình 7) from real multi-budget data.
- [x] Failure section gains by-size and by-budget breakdowns (Hình 10) when columns exist.
- [x] Memory view (Hình 9) renders from `peak_memory_mb` in `runs.metrics`; no results-schema
      migration required (first-class column optional).
- [x] Degrades gracefully to single-budget / no-characteristic states.

## Progress (2026-07-30)

Done + tested (`tests/test_memory.py` 4 + budget cases in `test_score_shapes.py` + by_size in
`test_failures.py`; full suite 117 green; verified live in the console + on ingested report data):
- `analysis/memory.py` — `memory_long` / `memory_matrix` / `memory_by_framework`, extracting
  `peak_memory_mb` from the `runs.metrics` JSON (`_peak` handles dict / JSON-string / None).
  `storage/repo.load()` now also exposes the `metrics` column (additive, like `info`).
- `analysis/score_shapes.budget_performance` (Hình 7) — normalized perf per (framework × budget).
- `analysis/failures.by_size` (Hình 10 panel B) — failure counts per size tier (reuses
  `with_characteristics`). Evaluation gains "Performance by budget", "Memory usage", and a
  "Failures by dataset size" panel; `explorer.memory_module()` added.
- Verified: on ingested report data, memory extracted (autogluon ~139 MB, flaml ~78 MB, h2o ~7 MB);
  on smoke, budget shows a single-budget note, failure-by-size renders, and the memory section is
  absent (no `peak_memory_mb`) — all graceful. Code-review: **DONE**, no blocking defects.

No results-schema migration was needed (memory rides in the existing `runs.metrics` JSON), so the
plan-level "no new result columns" non-goal held.

## Risk Assessment

- **Risk:** single-budget import makes Hình 7 trivial. **Mitigation:** Phase 4 creates a
  `constraints` row per budget; view degrades to a single bar with a note when only one exists.
- **Risk:** over-engineering a `peak_memory_mb` column + migration. **Mitigation:** default to
  reading memory from `runs.metrics` JSON (no migration); add a column only if querying by memory
  is actually needed.
