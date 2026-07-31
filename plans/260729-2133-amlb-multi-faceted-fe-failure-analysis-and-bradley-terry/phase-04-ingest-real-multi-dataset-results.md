---
phase: 4
title: "Ingest real multi-dataset results (reports JSON) + Kaggle datasets"
status: completed
priority: P1
effort: "1-2d"
dependencies: []
---

# Phase 4: Ingest real multi-dataset results (reports JSON) + Kaggle datasets

## Overview

The report's real pipeline is **not** the AMLB console — it is a separate harness on
`origin/main`: `scripts/run_automl.py` → `reports/run_*.json`, analysed in
`notebooks/analysis.ipynb`. Its result schema is clean and, crucially, already carries
**per-run memory and time budget**. This phase **bridges that pipeline into the console**:
ingest `reports/run_*.json` into the `runs` table (mapped via `storage.repo.load()`'s shape)
so every Evaluation view renders the real pipeline's output — plus import the underlying
datasets through the existing Kaggle pipeline so the catalog gets real characteristics.

Direction chosen with user (2026-07-30): **bridge into console** — console ingests
`reports/*.json`; downstream Phases 2/3/5/6 render it in Streamlit.

## Verified facts (2026-07-30)

**Reports JSON schema** (`reports/run_20260702_211007_f0f0d1.json`) — per result:
`dataset, framework, status, label, task, metric_name, metric_score, metric_score_raw,
metric_direction, best_model, best_config, resource_usage{duration_s, peak_memory_mb},
completed_at, error`. Top level: `run_id, time_budget, frameworks, started_at, results[]`.
→ **memory (`peak_memory_mb`) and budget (`time_budget`) are present** — Hình 9 (memory) and
Hình 7 (budget) become backable (this reverses the earlier AMLB-based "memory non-goal").
Committed data is small (3 datasets × 3 frameworks × budget 30); the full 12-dataset run is
produced by re-running `run_automl.py` (out of scope here — this phase ingests whatever JSON exists).

**Dataset acquisition via our Kaggle API (spec 006) — live-verified, 11/12 importable:**

| Dataset | ref `owner/slug` | file |
|---|---|---|
| adult_income | `uciml/adult-census-income` | adult.csv |
| breast_cancer | `uciml/breast-cancer-wisconsin-data` | data.csv |
| telco_churn | `blastchar/telco-customer-churn` | WA_Fn-UseC_-Telco-Customer-Churn.csv |
| abalone | `rodolfomendes/abalone-dataset` | abalone.csv |
| california_housing | `camnugent/california-housing-prices` | housing.csv |
| wine_quality | `uciml/red-wine-quality-cortez-et-al-2009` | winequality-red.csv |
| wine | `brynja/wineuci` | Wine.csv |
| obesity | `aravindpcoder/obesity-or-cvd-risk-classifyregressorcluster` | ObesityDataSet.csv |
| give_me_credit | `brycecf/give-me-some-credit-dataset` (mirror) | cs-training.csv |
| house_prices | `lespin/house-prices-dataset` (mirror) | train.csv |
| forest_cover | `uciml/forest-cover-type-dataset` (mirror) | covtype.csv |
| santander_satisfaction | **unresolved** — no public dataset mirror found | — |

Our `kaggle_client.parse_url` accepts only `/datasets/` URLs (competitions rejected by R1);
3/4 competition datasets have working dataset mirrors above. `santander` needs a valid ref,
manual download, or a competition-capable client (separate scope).

## Requirements

- Functional:
  - `ingest_report_json(path)` in `storage/ingest.py`: read a `reports/run_*.json`, insert
    `runs` rows, resolving/creating linked `datasets`, `methods`, `constraints`.
  - Map result → `runs`: `dataset→dataset`, `framework→method`, `task→datasets.task_type`,
    `metric_name→metric`, `metric_score(_raw)→result`, direction-normalized `score`,
    `resource_usage.duration_s→training_duration`, `resource_usage.peak_memory_mb→metrics JSON
    (+ optional column, see Phase 6)`, `time_budget→constraints.max_runtime_seconds`,
    `error/status→status (success | failure_*) + error_message`. `fold` = 0 (single split).
  - De-dupe on `(method, dataset, constraint, fold)` so re-import is idempotent.
  - Console reads it through the existing `storage.repo.load()` with **no view changes**.
  - Dataset import: reuse `ingest.kaggle_list` + `kaggle_import` with the verified refs so the
    catalog gets `infer_metadata`-derived `n_instances/n_features/minority_fraction/task_type`.
  - Import/Export control on the console (upload a report JSON; export `runs`→`results.csv`).
- Non-functional:
  - Reuse `infer_metadata`, `_insert_dataset`, `kaggle_import`; do not duplicate catalog logic.
  - Works in both DB modes (Postgres/SQLite) and offline.
  - No change to `analysis/*` or `console/views/*` beyond the import/export control.

## Architecture

Results ingestion today lives inline in `storage/runner.py` (a live AMLB run). Add a standalone
`ingest_report_json` to `storage/ingest.py`. Join keys mirror `repo.load()`:
`runs.method_id→methods.name`, `runs.dataset_id→datasets.name`, `runs.constraint_id→constraints.name`.
Datasets are resolved by name; if absent, import via the Kaggle refs above (→ `infer_metadata`
populates characteristics). Budget → get-or-create a `constraints` row named e.g. `30s`/`60s`/`300s`
with `max_runtime_seconds`. `repo.load()` already exposes `constraint`; memory rides in
`runs.metrics` JSON (a first-class column is a Phase 6 decision).

```
reports/run_*.json ──ingest_report_json()──▶ resolve datasets(Kaggle)/methods/constraints
                                          └─▶ insert runs (dedupe) ──▶ repo.load() ──▶ views
```

## Related Code Files

- Modify: `storage/ingest.py` — add `ingest_report_json(path)` + `_resolve_method` /
  `_resolve_constraint` (get-or-create by name); reuse `infer_metadata`, `_insert_dataset`,
  `kaggle_import`, `insert(runs)`.
- Reference (read): `reports/run_*.json` (schema), `storage/repo.py` (`load()` target shape),
  `storage/runner.py` (inline results→runs mapping to mirror), `storage/models.py`.
- Modify: `console/views/evaluation.py` or `training.py` — "Import report JSON" + "Export
  results.csv" control (out of `analysis/*`).
- Create: `tests/test_ingest_report_json.py` — fixture JSON (≥2 datasets, ≥2 frameworks,
  1 failure `error`) → assert `runs` rows + links + memory-in-metrics + dedupe on re-import.

## Implementation Steps

1. Read the committed `reports/run_*.json`; confirm the field mapping above against it.
2. Implement `ingest_report_json(path)`: parse JSON; per result resolve-or-create dataset
   (Kaggle import when absent), method, constraint; insert `runs` with mapped columns +
   `resource_usage` into `metrics` JSON.
3. Idempotent de-dupe on `(method, dataset, constraint, fold)`.
4. Add the Import/Export console control.
5. Write `tests/test_ingest_report_json.py`; run `pytest tests/test_ingest_report_json.py -q`.
6. Ingest the committed JSON; verify `repo.source() == "db"` and Evaluation shows the real
   datasets/frameworks with memory + budget available downstream.

## Success Criteria

- [x] `ingest_report_json` loads a `reports/run_*.json` into `runs` with correct
      dataset/method/constraint links + memory in `metrics`; re-import is idempotent.
- [x] Failure results (`error` set) land as `failure_*` with `error_message` (Phase 1 classifies them).
- [x] Catalog characteristics populate from local dataset files on import (verified: breast_cancer
      569×30, california 20640×8, wine 178×13 — no `unknown`); Kaggle refs for 11/12 datasets
      verified live for on-demand import (bulk import deferred, not required for this phase).
- [x] Evaluation renders the real results via unchanged `repo.load()`; Import/Export control works.
- [x] Tests pass offline (fixture JSON; no live Kaggle/DB required in the unit test).

## Progress (2026-07-30)

**Done + tested (`tests/test_ingest_report_json.py`, 4 cases; full suite 92 green):**
- `storage/ingest.ingest_report_json(path)` — maps `reports/run_*.json` → `runs`, get-or-create
  datasets/methods/constraints, memory in `runs.metrics`, idempotent on `(method,dataset,constraint,fold)`.
- Verified on the real committed JSON: 9 runs, correct binary/multiclass/regression, score
  orientation correct, characteristics populated from local `dataset/*/train.csv` (breast_cancer
  569×30 minority 0.37, california 20640×8, wine 178×13 — matches `report_v2.md`).
- Code-review fixes applied:
  - **H1** — `storage/repo.load()` now selects `error_message` as `info` so `analysis/failures`
    classifies DB-sourced failures correctly (was silently "unknown"); asserted via
    `failures.by_category(repo.load())`.
  - **M3** — `result` stored already-oriented (= `score`), matching the `load_results`/`repo.load`
    contract (rmse negative).
  - **M2** — in-batch `seen` set dedupes duplicate `(method,dataset,constraint,fold)` within one file.
  - **L6** — `meta.json` opened via `with`.

**Console Import/Export UI — done:** `console/views/evaluation.py` now has an "Import / Export
results" expander (before the empty-state stop, so import works when the DB is empty):
`st.file_uploader` → `ingest.ingest_report_bytes` (added a bytes wrapper; core factored into
`_ingest_report`), plus a "Export results.csv" `download_button`. Compile + full suite (92) green.

**Deferred (still open in this phase):**
- Bulk Kaggle dataset import via the verified refs (side-effecting download — needs go-ahead).
- Not yet ingested into the real `console.db` (the user can now click Import in the console).

**Known limitations (low, accepted):**
- L4 — get-or-create binds runs to an existing dataset row by name and won't backfill NULL
  characteristics on a pre-existing row.
- L5 — `_task_type_from` maps `auc`→binary unconditionally (overridden when a real `train.csv` exists).
- DB `info` carries the error message (keyword classification works); the duration-vs-budget
  timeout heuristic in `analysis/failures` remains CSV-only (budget/duration not in `repo.load`).

## Risk Assessment

- **Risk:** `santander_satisfaction` has no working Kaggle dataset ref. **Mitigation:** proceed
  with 11/12; santander handled later (manual download / competition-capable client) — logged, not silent.
- **Risk:** committed JSON is a tiny 3-dataset run → console still sparse. **Mitigation:** the
  ingest is data-agnostic; the full 12-dataset run is produced by re-running `run_automl.py`
  (separate effort). Views degrade gracefully meanwhile.
- **Risk:** result `dataset`/`framework` names differ from catalog. **Mitigation:** get-or-create
  by normalized name; never hard-fail a row; log unmatched.
- **Risk:** mass Kaggle download side effects (some datasets large, e.g. forest_cover). **Mitigation:**
  import on demand with the existing size guard (`KAGGLE_MAX_FILE_MB`); confirm before bulk download.
