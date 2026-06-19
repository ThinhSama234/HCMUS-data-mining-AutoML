# Contract: AMLB user-dir config schemas

What our `amlb_userdir/` files must contain so AMLB runs the intended datasets under the intended protocol. Exact AMLB YAML keys are confirmed at setup; the shape below is the contract our scripts and report rely on.

## benchmarks/*.yaml — dataset selection

A list of tasks, each referencing an OpenML task by id:

```yaml
- name: credit-g
  openml_task_id: 168757
- name: vehicle
  openml_task_id: 190146
- name: Moneyball
  openml_task_id: 167210
```

- `mvp.yaml` — the MVP-3 above (one per task type, all small).
- `thesis.yaml` — the ~12 tasks from [research.md](../research.md) D3, spanning 3 task types × 3 size tiers (+ one imbalanced, + one real-world `churn`).
- **Invariant**: every entry resolves to a real OpenML task id; the set covers all three task types and ≥3 size tiers (SC-003).

## constraints.yaml — protocol/budgets

```yaml
smoke:   { folds: 1,  max_runtime_seconds: 600,   cores: 8 }
1h:      { folds: 10, max_runtime_seconds: 3600,  cores: 8 }
4h:      { folds: 10, max_runtime_seconds: 14400, cores: 8 }
```

- **Invariant**: a constraint is applied **identically** to every framework on a given task (FR-003, SC-002). `cores`/memory are fixed across frameworks.

## frameworks (selection passed on the CLI or overridden here)

Runners: `H2OAutoML`, `flaml`, `AutoGluon` (best-quality preset) + baselines `constantpredictor`, `RandomForest`, `TunedRandomForest`.

- **Invariant**: frameworks run with intended presets only; no per-task hand-tuning (FR-013). AutoGluon GPU enabled (D7).
