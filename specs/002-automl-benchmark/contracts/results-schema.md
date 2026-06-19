# Contract: AMLB results CSV → analysis layer

The boundary between "running" (AMLB) and "analysis" (our scripts). AMLB writes one results CSV; our `analysis/` reads these columns. Column names are as produced by AMLB — **confirm exact spellings against the tool's output at first setup** (D-open-items); the analysis must tolerate extra columns it does not use.

## Required input columns (consumed by analysis)

| Column | Meaning | Used by |
|---|---|---|
| `framework` | runner name (H2OAutoML / flaml / AutoGluon / baselines) | all |
| `task` | dataset/task name | all |
| `fold` | fold index | aggregation |
| `type` | binary / multiclass / regression | metric selection, rankings (never mix types) |
| `result` | primary metric value for the task type | rankings, Pareto |
| `metric` | metric name (auc / logloss / rmse) | validation that the right metric was used |
| `training_duration` | seconds spent training | budget-adherence reporting (FR-015) |
| `predict_duration` | inference time | Pareto (FR-009) |
| `models_count` | models built | context |
| `seed` | random seed | reproducibility check |
| `framework_version` / `version` | resolved framework version | reproducibility record |
| `info` / `error` | failure details when not successful | failure categorization (FR-006, D9) |

## Invariants (the contract)

- One row per `(framework, task, fold)` — the `Run` identity in [data-model.md](../data-model.md).
- A row is either a **success** (`result` present, `info`/`error` empty) or a **failure** (`result` empty/NaN, `info`/`error` populated). Never silently absent (SC-001).
- `metric` is constant within a `type` across all frameworks (proves FR-003).
- Higher `result` is better for auc; for logloss/rmse lower is better → analysis normalizes direction per metric before ranking.

## Failure → category mapping (D9)

| Signal in `info`/`error` | Category |
|---|---|
| out-of-memory, segmentation fault, OOM | `memory` |
| exceeded time / leniency, timeout | `time` |
| class missing in split, unsupported feature type, NaN target | `data` |
| framework exception / traceback (other) | `implementation` |
