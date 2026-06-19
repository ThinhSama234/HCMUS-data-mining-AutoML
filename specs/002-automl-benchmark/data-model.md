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

## Key relationships (summary)

```text
Framework ─┐
Baseline  ─┼─> Run (× Task × fold, under one Protocol) ─> ResultRecord ─┐
Task ──────┘                              └─ Failure (if not success) ──┴─> Report & Artifacts
```
