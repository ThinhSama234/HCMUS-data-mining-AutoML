---
phase: 1
title: "Statistical significance + confidence"
status: completed
priority: P1
effort: "1.5-2d"
dependencies: []
---

# Phase 1: Statistical significance + confidence

## Overview

Close the biggest analytical gap (checklist §5): today there is only average-rank + a Bradley-Terry
*approximation*, no significance test. Add a **Friedman test** (are the frameworks different at all?)
+ **Nemenyi post-hoc** rendered as a **critical-difference (CD) diagram**, plus ±std / confidence on
the mean charts — the standard, defensible way to compare multiple AutoML frameworks over many datasets.

## Requirements

- Functional:
  - Friedman test across frameworks over datasets (blocks = datasets, treatments = frameworks) →
    statistic + p-value + a plain verdict ("frameworks differ significantly, p=…").
  - Nemenyi post-hoc → pairwise significance + the **critical difference** value; render a CD diagram
    (average-rank axis with frameworks joined by a bar when their rank gap < CD).
  - Add ±std / CI to the mean charts (leaderboard, by-characteristic) using the per-fold std that
    `rankings.per_task_scores` already computes.
- Non-functional:
  - Pure logic in `analysis/significance.py`; the view only renders (INV-1/INV-2).
  - Needs **complete blocks** (frameworks present on the same datasets) — restrict to the common
    dataset set and say so; require ≥3 frameworks and ≥ a few datasets, else info-degrade
    ("not enough frameworks/datasets for a significance test").

## Architecture

Friedman needs a datasets×frameworks matrix of one score per cell — reuse the per-(dataset,framework)
mean the ranking layer already builds (`rankings.average_ranks` ranks within task; `per_task_scores`
gives `score_mean`). Build the matrix from `repo.load()` (higher-is-better `score`), keep only
frameworks that appear on every dataset in the selection (Friedman requires complete blocks; log how
many datasets/frameworks were dropped).

Stats backend (KISS, one new dep): prefer **`autorank`** — a single `autorank(df)` runs
Friedman+Nemenyi and `plot_stats()` draws the CD diagram; fall back to `scipy.stats.friedmanchisquare`
+ `scikit_posthocs.posthoc_nemenyi_friedman` + a hand-drawn CD diagram if `autorank` proves heavy.
The CD diagram is a matplotlib figure → render with `st.pyplot` (mirrors `explorer.export_headline_figures`,
which already uses matplotlib Agg). Everything else (bar charts) stays Plotly.

```
repo.load() ──▶ significance.score_matrix (datasets × frameworks, complete blocks)
            ├─▶ friedman(matrix) → stat, p, verdict
            └─▶ nemenyi/cd(matrix) → avg ranks + CD → CD diagram (matplotlib)
Evaluation "Statistical significance" section: verdict + CD diagram + a pairwise p table
```

## Related Code Files

- Create: `analysis/significance.py` — `score_matrix(df)`, `friedman(df)`, `nemenyi(df)`,
  `critical_difference(df)` (avg ranks + CD), `cd_diagram(df) -> matplotlib Figure`, `main(argv)` CLI.
- Modify: `analysis/explorer.py` — `significance_module()` via `_optional_module`.
- Modify: `console/views/evaluation.py` — a "Statistical significance" section (Friedman verdict +
  `st.pyplot(cd_diagram)` + pairwise-p table), guarded by module-present + enough-data; add ±std
  error bars to the leaderboard / by-characteristic charts using `per_task_scores` std.
- Modify: `requirements.txt` — add `scipy` (+ `autorank` or `scikit-posthocs`), pinned with `>=`.
- Create: `tests/test_significance.py` — synthetic matrix where one framework strictly dominates →
  Friedman significant (p<0.05) + that framework has the best (lowest) avg rank; a no-difference
  matrix → not significant; <3 frameworks / incomplete blocks → graceful empty/degrade.

## Implementation Steps

1. Add `analysis/significance.py`: build the complete-block score matrix from `repo.load()`; implement
   `friedman` / `nemenyi` / `critical_difference` / `cd_diagram`; degrade to a clear "insufficient
   data" result (not an exception) when blocks are too few/incomplete.
2. Pick the stats backend (try `autorank` first) and add the dep to `requirements.txt`; keep the
   import lazy inside the functions so importing `analysis` never pulls scipy.
3. Wire `significance_module()` into `explorer.py`.
4. Add the Evaluation section (verdict + CD diagram via `st.pyplot` + pairwise table), guarded.
5. Add ±std error bars to the mean charts from `per_task_scores` std.
6. Write `tests/test_significance.py`; run `pytest tests/test_significance.py -q`. Verify live on an
   ingested multi-dataset run (or a synthetic one) that the CD diagram renders without error.

## Success Criteria

- [x] `analysis/significance.py` computes Friedman (stat+p) and a Nemenyi CD, unit-tested on a
      known-significant and a known-null matrix; incomplete/too-few blocks degrade gracefully.
- [x] Evaluation shows the Friedman verdict + a CD diagram + a pairwise-p table.
- [ ] Mean charts carry ±std / CI, not bare means. → **moved to Phase 2** (which owns mean±std display;
      current committed data is single-fold so std is empty anyway).
- [x] Pure `analysis/*` + `_optional_module` + graceful degrade; `scipy` added to requirements.

## Progress (2026-07-31)

Done + tested (`tests/test_significance.py`, 10 cases; full suite 129 green):
- `analysis/significance.py` — `score_matrix` (complete-block reduction via a greedy drop-most-missing
  row/column), `friedman` (scipy), `critical_difference` + `nemenyi` (hand-rolled Nemenyi CD, no
  `autorank`/`scikit-posthocs` dep), `cd_diagram` (matplotlib Demšar diagram). `explorer.significance_module()`
  + a guarded Evaluation "Statistical significance" section (verdict + `st.pyplot` CD diagram + pairwise table).
- **Verified correct** by code review: CD constant `q_α=studentized_range/√2`, Friedman orientation,
  rank direction all match Demšar (2006); CLI smoke on the ingested run gives a sensible Friedman p=0.097
  (not significant on only 3 datasets — the motivation for Phase 5).
- **Code-review fixes:** (Critical) NaN p-value on fully-tied input now **degrades** to
  `significant: None` instead of reporting a bogus "not significant · p=nan"; (Medium) the greedy
  complete-block reduction no longer lets one sparse framework collapse the dataset count; (Medium)
  matrix-vs-long-df dispatch is now an explicit structural check, not `index.name`. All covered by new tests.
- `scipy>=1.10` declared in `requirements.txt` (already present transitively).

## Risk Assessment

- **Risk:** too few datasets/frameworks → the test is meaningless or errors. **Mitigation:** require
  complete blocks + minimums; show "not enough data for a significance test (stabilizes with the full
  suite)" instead of a spurious result. Strongest once Phase 5 lands more datasets.
- **Risk:** `autorank` is a heavy/opinionated dep. **Mitigation:** fall back to `scipy` +
  `scikit-posthocs` + a small hand-drawn CD diagram; keep the stats backend behind our functions.
- **Risk:** mixing matplotlib (CD diagram) into a Plotly page. **Mitigation:** `st.pyplot` on an Agg
  figure, exactly as `export_headline_figures` already does; scope matplotlib to this one section.
