---
phase: 1
title: "Failure analysis view"
status: completed
priority: P1
effort: "1.5-2d"
dependencies: []
---

# Phase 1: Failure analysis view

## Overview

Turn the single raw "N failures" KPI into the paper's failure analysis: classify every
failed run into **Memory / Time / Data / Implementation** and visualize the breakdown by
framework and by time budget. This is a headline novelty of the AMLB paper (§6.4 + App. D)
and the data is already present — no runner changes needed.

## Requirements

- Functional:
  - Classify each failed run (`success == False`) into one of `memory | time | data | implementation | unknown` from the `info` message (+ `duration` vs budget for time).
  - Aggregate counts by category, by framework, and by budget (`constraint`).
  - Render a **Failure analysis** section on the Evaluation page (below Per-task scores).
- Non-functional:
  - Pure logic in `analysis/failures.py`; FE only renders (INV-2, single source of truth).
  - Graceful degrade: if the module or `info` column is absent, show an info message (US3/US4 pattern).
  - Unit-tested classification with representative messages.

## Architecture

Data facts (verified):
- `load_results.load_results` already sets `success = result_num.notna()`; failures keep an
  `info` message (loader docstring: "Failures carry an empty result plus an info/error message").
- `constraint` column = time budget (maps to the paper's 1h vs 4h comparison).
- `duration` = wall-clock of the run (approx "when it failed").

Classification heuristic (keyword match on lowercased `info`, order matters):
1. **memory** — `memory`, `oom`, `out of memory`, `segmentation fault`, `sigkill`, `sigsegv`.
2. **time** — `timeout`, `time limit`, `exceeded ... time`, or `duration >= budget * leniency` when `info` is empty.
3. **data** — `imbalance`, `only one class`, `n_splits`, `minority`, `stratif`, `nan`, `single class`.
4. **implementation** — any remaining non-empty `info` (framework bug / traceback).
5. **unknown** — failed but no `info` and not clearly a timeout.

Keyword tables live as module-level constants so they're easy to extend and to unit-test.

## Related Code Files

- Create: `analysis/failures.py` — `classify(row) -> str`, `failure_table(df) -> DataFrame[category, framework, constraint, n]`, `by_category(df)`, `by_framework(df)`, `main(argv)` CLI (mirror `pareto.py`/`by_characteristics.py`).
- Modify: `analysis/explorer.py` — add `failures_module()` via existing `_optional_module("failures")`.
- Modify: `console/views/evaluation.py` — add a "Failure analysis" section (stacked bar: category × framework; small table by budget); reuse `fdf` already filtered. Keep the existing Coverage KPI.
- Create: `tests/test_failures.py` — classification + aggregation tests with sample `info` strings (incl. the yeast/wine-quality imbalance case from App. D.1).

## Implementation Steps

1. Write `analysis/failures.py` with the keyword constants + `classify` + aggregation functions + CLI. Read only `df[~df["success"]]`.
2. Add `failures_module()` to `analysis/explorer.py` (graceful `_optional_module`).
3. Add the Evaluation section: Plotly stacked bar (x = framework, color = category) + a compact `by budget` table; guard with `if failures is None: st.info(...)`.
4. Write `tests/test_failures.py`; run `pytest tests/test_failures.py -q`.
5. Sanity-check against a real failing run (e.g. `results/job_*/results.csv` rows with empty `result`).

## Success Criteria

- [x] `analysis/failures.py` classifies the 4 categories + unknown, unit-tested.
- [x] Evaluation page shows failures broken down by category × framework and by budget.
- [x] No change to rankings/coverage numbers; failed runs still excluded from ranks.
- [x] Section degrades gracefully when there are zero failures or no `info` column.

## Risk Assessment

- **Risk:** `info` message formats vary per framework → misclassification. **Mitigation:** keyword tables + `unknown` bucket + tests; classification is descriptive, not load-bearing.
- **Risk:** smoke results have few/no failures → empty view. **Mitigation:** graceful empty-state; note it fills with the full suite (same caveat already used for by-characteristic).
