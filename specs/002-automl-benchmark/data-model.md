# Phase 1 Data Model: AutoML Framework Benchmark

These are the conceptual entities of the benchmark and analysis. They map to AMLB inputs/outputs and our analysis layer — not to a database (storage is files/CSV).

## Entities

### Framework (under test)
- **Fields**: `name` (H2OAutoML | flaml | AutoGluon), `version` (recorded per run), `preset/config` (e.g., AutoGluon best-quality), `optimization_approach` (for reporting).
- **Relationships**: produces many `Run`s.
- **Validation**: must be one of the three target frameworks; preset applied equally across tasks (FR-013).

### Baseline
- **Fields**: `name` (constantpredictor | RandomForest | TunedRandomForest), `version`.
- **Relationships**: produces many `Run`s; used as the reference in rankings/eval gate (Constitution IV).
- **Validation**: present for every task that the frameworks run (FR-001).

### Task (dataset)
- **Fields**: `openml_task_id`, `name`, `task_type` (binary | multiclass | regression), `n_instances`, `n_features`, `class_ratio` (classification only), `target`.
- **Relationships**: evaluated by every Framework and Baseline under one `Protocol`.
- **Validation**: from the recorded AMLB suite; `task_type` drives the metric (FR-003); selection spans ≥3 size tiers and all 3 types (SC-003).
- **Derived**: `size_tier` (small <2k | medium 2k–50k | large >50k), `dim_tier`, `balance_tier` — used by `by_characteristics` (FR-010).

### Protocol (constraint)
- **Fields**: `name` (smoke | 1h | 4h), `folds` (1 for smoke, 10 final), `max_runtime_seconds` (~600 | 3600 | 14400), `cores`, `max_mem_mb`, `metric_by_type` (auc/logloss/rmse).
- **Relationships**: applied identically to every (Framework × Task) (FR-003, FR-014).
- **Validation**: a run's recorded config must match its declared Protocol (SC-002).

### Run  *(the atomic unit)*
- **Identity**: (`framework` × `task` × `fold`).
- **Fields**: `status`, `score` (primary metric), `metric`, `training_duration`, `predict_duration` (inference time), `models_count`, `seed`, `framework_version`, `dataset_version`, `info`, `error`.
- **State transitions**: `queued → running → success` **or** `→ failure(category)` where category ∈ {memory, time, data, implementation} (FR-006, D9). Terminal states only; no silent drop.
- **Validation**: every planned Run reaches a terminal state with a recorded score *or* a categorized failure (SC-001); test/val partition never used for training (FR-014).

### ResultRecord  *(aggregation per Framework × Task)*
- **Fields**: `mean_score`, `std_score`, `completed_folds`, `missing_folds`, `coverage` (= completed/total).
- **Relationships**: aggregates the folds' `Run`s; feeds rankings, Pareto, coverage.
- **Validation**: mean/std computed only over completed folds; `missing_folds` reported, never imputed (FR-007).

### Failure
- **Fields**: `category` (memory | time | data | implementation), `message`, `context` (framework, task, fold), `source` (parsed from Run.info/error).
- **Relationships**: belongs to a failed `Run`; aggregated into coverage (FR-006).

### Report & Artifacts
- **Fields**: `rankings_table`, `coverage_table`, `pareto_table/plot`, `by_characteristic_table`, `reproducibility_guide`, `written_report`.
- **Relationships**: derived from `ResultRecord`s and `Failure`s; the report cites the AMLB paper and lists pitfalls avoided (FR-012, SC-005/006).
- **Validation**: regenerable from recorded data by one command (FR-011, SC-004).

### ResultsDashboard  *(US6 — presentation, not stored data)*
- **Fields**: `data_source` (path to a results CSV / tidy frame from `load_results`), `views` ({ranking, pareto, by_characteristic}), `filters` ({framework, task_type, dataset, budget}), `exports` (static headline figures for the report).
- **Relationships**: reads `ResultRecord`s/`Failure`s via the analysis layer; renders by calling `rankings.py` / `pareto.py` / `by_characteristics.py` (single source of truth — no recomputation logic of its own).
- **Validation**: operates on recorded data only and triggers no benchmark run; every filter change re-derives views consistently from the same records (FR-016, SC-008).

### IntegrationSkill  *(US7 — developer tooling, not stored data)*
- **Fields**: `input_contract` (Python, pip-installable, exposes `fit`/`predict`), `rules/preconditions` (enforced), `emitted_artifacts` (`amlb_userdir/extensions/<Name>/{__init__.py, exec.py, setup.sh, requirements.txt}` + an `amlb_userdir/frameworks.yaml` entry with `module: extensions.<Name>`), `verification` (smoke-suite run yielding scored predictions).
- **Relationships**: produces a new `Framework`-shaped module that the AMLB harness can run as a `Run` source; does **not** add to the set of frameworks under test (FR-001) and does not score (the harness scores — FR-003/FR-014).
- **State transitions**: `precondition-check → (pass) scaffold → verify(smoke) → done` **or** `(fail) reject(reason)` with no partial module written (US7 acceptance #2, SC-009).

## Key relationships (summary)

```text
Framework ─┐
Baseline  ─┼─> Run (× Task × fold, under one Protocol) ─> ResultRecord ─┐
Task ──────┘                              └─ Failure (if not success) ──┴─> Report & Artifacts
                                                                            │
                                                          ResultsDashboard ─┘  (read-only views + filters, US6)

IntegrationSkill ─(scaffold + smoke-verify)─> new Framework-shaped module ─> Run  (US7; not in FR-001 set)
```
