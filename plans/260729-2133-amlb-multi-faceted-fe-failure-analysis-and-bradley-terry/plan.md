---
title: "AMLB multi-faceted FE — report↔console E2E reconciliation"
description: "Make the console reproduce the report's multi-faceted analysis figures end-to-end from real data (Option C): ingest real results, close the analysis gaps (failure, characteristics, Bradley-Terry, score/time/memory/budget figures)."
status: completed
priority: P1
effort: "6-9d"
tags: [analysis, frontend, evaluation, thesis, ingest]
created: 2026-07-29
updated: 2026-07-30
---

# AMLB multi-faceted FE — report↔console E2E reconciliation (Option C)

## Overview

`report_v2.md` already presents 11 figures across the paper's multi-faceted analysis
(dataset characteristics, normalized/raw scores, score-vs-time, perf-by-budget, inference,
memory, failures, Bradley-Terry). **The report existed first; the E2E code to produce those
analyses in the console does not.** The console's live results are a **3-dataset `smoke`**
run with different frameworks — so the Evaluation page and the report disagree, violating the
repo's own invariant INV-2 ("the Evaluation page and the report can never disagree",
`analysis/explorer.py`).

Decision (with user) = **Option C**: make the console the reproducible engine for the report.
Path: **ingest the real results under app management** (the app manages + downloads data;
CSV/parquet fallback where a live run isn't feasible), then close each analysis gap as a pure
`analysis/*` module discovered by `explorer._optional_module` and rendered with graceful
degrade — the existing single-source-of-truth pattern. Bradley-Terry stays a **lightweight,
honest Python approximation** (no R/rpy2).

### Map: report figure ↔ current E2E code ↔ this plan

| Report figure(s) | Current E2E backing | This plan |
|---|---|---|
| Overall ranking | `rankings.py` + leaderboard | done |
| Inference Pareto | `pareto.py` | done |
| Failures (Hình 10) | `failures.py` + view | **Phase 1 (done)**; enriched in Phase 6 |
| Dataset characteristics grouping | `by_characteristics.py`, **5 hardcoded tasks** | **Phase 2** (catalog) |
| Bradley-Terry (Hình 11) | none | **Phase 3** |
| Real 12-ds / 4-fw / 2-budget data | **not in repo** (smoke only) | **Phase 4 (blocker)** |
| Dataset overview + score/time (Hình 1,2,4,5,6,8) | none / partial | **Phase 5** |
| Perf-by-budget (Hình 7) + memory (Hình 9) + failure enrichment (Hình 10) | budget + `peak_memory_mb` in reports JSON | **Phase 6** |
| Target-dist (Hình 3) | needs raw-file plotting | **out of scope** — static in report |

**Validated scope (2026-07-30, revised for reports-JSON source):** the real pipeline is
`scripts/run_automl.py` → `reports/run_*.json` (on `origin/main`), whose schema **carries
`peak_memory_mb` and `time_budget`** — so memory (Hình 9) and budget (Hình 7) are backable
after all (reverses the earlier AMLB-based non-goal). Direction = **bridge into console**:
Phase 4 ingests `reports/*.json`; datasets come via the Kaggle pipeline (11/12 refs
live-verified). Only Hình 3 (target-dist) stays static. Acceptance ≈ **10/11 figures**.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Categorized failure-analysis view (by category, framework, budget) | P1 |
| 2 | Dataset characteristics from the real catalog (not 5 hardcoded tasks) | P1 |
| 3 | Ranking-flip / Bradley-Terry-style view (honest Python approximation) | P2 |
| 4 | Real multi-dataset results under app management so views ≡ report (INV-2) | P1 |
| 5 | Reproduce the remaining score/time/dataset-overview figures E2E | P2 |
| 6 | Perf-by-budget + enriched failure panels (memory dropped) | P3 |

## Phases

| # | Phase | Status | Priority | Depends |
|---|-------|--------|----------|---------|
| 1 | [Failure analysis view](./phase-01-start.md) | Done | P1 | — |
| 2 | [Real dataset characteristics from catalog](./phase-02-real-dataset-characteristics-from-catalog.md) | Done | P1 | — |
| 3 | [Bradley-Terry ranking-flip (Python approx)](./phase-03-bradley-terry-ranking-flip-python-approximation.md) | Done | P2 | 2, 4 |
| 4 | [Ingest real multi-dataset results](./phase-04-ingest-real-multi-dataset-results.md) | Pending | P1 | — |
| 5 | [Figure-parity analysis views](./phase-05-figure-parity-analysis-views.md) | Done | P2 | 2, 4 |
| 6 | [Budget dimension + failure enrichment](./phase-06-memory-and-budget-dimension.md) | Done | P3 | 2, 4 |

Recommended order: **4 → 2 → 3 → 5 → 6** (Phase 1 already done). Phase 4 is the true blocker —
without real data every downstream view is smoke and Bradley-Terry/boxplots are meaningless.
Phases 2/3/5 code can be *written* against fixtures independently, but only *light up* after 4.
Phase 6 (budget + failure enrichment) is cheap once Phase 4 imports ≥2 budgets and Phase 2
populates characteristics.

## Success Criteria

- [x] Failure-analysis section: Memory / Time / Data / Implementation, by framework and budget.
- [ ] **Real results are managed by the app** (imported into `runs` or `results.csv`); the
      Evaluation page renders the report's datasets/frameworks, not the 3-dataset smoke set.
- [ ] By-characteristic and ranking-flip views read `n_instances / n_features /
      minority_fraction / task_type` from the **catalog**, covering all datasets in the results.
- [ ] **Ranking-flip** section names the characteristic + split where ranking changes, labelled
      as an approximation of the paper's Bradley-Terry trees.
- [ ] Evaluation/Datasets reproduce the report's score, score-vs-time, inference, and
      dataset-overview figures from real data (Hình 1,2,4,5,6,8).
- [ ] Perf-by-budget renders from ≥2 budgets; failure section gains by-size + by-budget panels.
- [ ] All new logic in pure `analysis/*` modules with pytest coverage; FE only renders and
      degrades gracefully when a module/column is absent.
- [ ] Catalog characteristics (`n_instances/n_features/minority_fraction`) are populated for
      imported datasets via `infer_metadata` — no `unknown` tiers for the report's datasets.

## Non-Goals

- Full statistical Bradley-Terry via R (`partykit`/`psychotree`). Out of scope (lightweight decision).
- Anytime-performance capture (the paper's own stated limitation).
- Re-running the full 12-dataset suite locally — infeasible on this host (needs CI/Linux; existing
  runner limitation). Phase 4 uses the import path instead.
- **Target-distribution figure (Hình 3)** — needs raw dataset-file plotting; stays static in the report.
- Re-running `run_automl.py` for the full 12-dataset × 60/300s × 4-framework suite — separate
  effort; this plan ingests whatever `reports/*.json` exists (committed run is small).
- Competition-capable Kaggle client — our API is datasets-only; competitions use dataset mirrors
  (`santander` unresolved). Extending the client is separate scope.

**Scope note (revised 2026-07-30, reports-JSON source):** memory is **back in scope** —
`reports/*.json` carries `peak_memory_mb`, so Phase 6 backs Hình 9 by reading it from
`runs.metrics` JSON (no results-schema migration; a first-class `peak_memory_mb` column is an
optional Phase 6 decision). Catalog characteristics come from `infer_metadata` on Kaggle-imported
dataset files (a catalog write, not a results-schema change).

## Backlog (future enhancements)

- **HTML report export (not just CSV).** Phase 4's Export button currently emits `results.csv`
  only. Add a "Export HTML report" that renders the full Evaluation output — all charts (leaderboard,
  Pareto, by-characteristic, failures, and the Phase 3/5/6 figures) plus the score tables — into a
  single self-contained HTML file, mirroring `report_v2.md`. Reuse the pure `analysis/*` functions
  and the Plotly figures (`fig.to_html`) or the existing `explorer.export_headline_figures` path;
  keep it in the console/export layer, not `analysis/*`. Do after the figure phases (5/6) so all
  charts exist to embed. Requested by user 2026-07-30.

### Evaluation-protocol hardening — a rigorous, reproducible AMLB-style benchmark (2026-07-31)

Gap analysis vs the paper's evaluation-rigor checklist (see `plans/reports/` if captured). **Decision:**
the in-process `scripts/run_automl.py` (single-split, sklearn, 3 frameworks) is **frozen** — it only
backs the *current* `report_v2.md`. The **AMLB console runner** (`storage/runner.py` + Docker
per-framework, k-fold, baselines, `predict_duration`) is the **final code**; all items below target it.

Already satisfied by the AMLB path (no work): per-framework Docker isolation, default presets (no
hand-tune), failure capture + categorization + coverage% (`analysis/failures.py`), cross-task score
normalization (`load_results.score` / `score_shapes.normalized_scores`), separate inference time
(`predict_duration` → Pareto), constant/RandomForest baselines.

- **[Protocol] k-fold CV → mean ± std, with an explicit split/eval config on the Training page.**
  Closes checklist §1. Surface & persist the evaluation protocol as run config: number of folds
  (k-fold CV, not single split), **stratified** split for classification, a fixed split **seed**
  (+ optional multi-seed repetition to capture AutoML non-determinism), and shared fold indices
  across frameworks. Report per-(dataset×framework) **mean ± std** over folds. AMLB already produces
  folds; the work is (a) a Training-page config surface for folds/seed/stratify, (b) making the
  Evaluation tables/charts show mean ± std from the multi-fold `runs`. Fixes checklist item #1.

- **[Fairness] Redesign the Training budget & resource model, made explicit.** Closes checklist §3.
  Rework the budget UX/config so every framework provably gets the **same time budget + the same
  CPU/RAM allocation**, and log the allocated + actual resources per run to prove it (today
  `constraints` has `max_runtime_seconds`/`cores`/`max_mem_mb` but the Training page doesn't surface
  or enforce/record them clearly). Make the budget a first-class, visible part of the run plan.

- **[Statistics] Significance testing + confidence on charts.** Closes checklist §5 (biggest gap —
  none today beyond avg-rank + the Bradley-Terry approximation). Add `analysis/significance.py`:
  **Friedman test** across frameworks + **Nemenyi post-hoc** → a **critical-difference (CD) diagram**
  (via `scipy.stats` and/or `autorank`), rendered as an Evaluation section. Add **CI / ±std error
  bars** to the mean charts (normalization is already done). New dep: `scipy` (+ optional `autorank`).

- **[Reproducibility] Pin & record framework versions; one-command rerun.** Closes checklist §6.
  Pin AutoML framework versions (image digests already exist on `methods`; surface/record them),
  write `framework_version` into every `runs` row and into any exported report, and document a
  single reproduce command with a fixed seed. Today deps use `>=` and the report JSON records no
  version.

- **[Scope] Expand the suite to ~10–20 datasets spanning 3 task-types × size/dim/class-balance
  tiers,** recording n / #features / class ratio per dataset (the catalog + `infer_metadata`
  already compute these; the gap is dataset breadth + committing the data/results). Data-collection
  task; pairs with the CV item above.

<!-- slug: amlb-multi-faceted-fe-failure-analysis-and-bradley-terry -->
