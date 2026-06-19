# Quickstart: validate the benchmark end-to-end (MVP first)

Proves **User Story 1** (a fair head-to-head comparison) on 3 small datasets, then shows how to scale. This is a validation/run guide — implementation detail lives in `tasks.md` and the code.

## Prerequisites

- Linux with Python 3.11; GPU + CUDA for AutoGluon best-quality (optional for the smoke run).
- The `automlbenchmark` (AMLB) tool installed per its docs (clone + `pip install -r requirements.txt`, or the packaged CLI). Confirm the exact invocation at setup.
- This project's `automl-benchmark/amlb_userdir/` with `benchmarks/mvp.yaml` and `constraints.yaml` (see [benchmark-config-schema.md](./contracts/benchmark-config-schema.md)).

## Step 1 — MVP smoke run (local mode, ~10-min budget, 1 fold)

Run each framework + baseline on the MVP-3 datasets in local mode. Conceptually, for each runner in
`H2OAutoML flaml AutoGluon constantpredictor RandomForest TunedRandomForest`:

```bash
python runbenchmark.py <runner> mvp smoke -m local -u automl-benchmark/amlb_userdir
```

(`scripts/run_mvp.sh` loops the runners.) Expect this to finish in a few hours on a single machine.

**Expected outcome**: a results CSV under `results/` with one row per `(framework, task, fold)` — successes carry a `result`; any failures carry `info`/`error` (none silently missing). See [results-schema.md](./contracts/results-schema.md).

## Step 2 — First comparison (the MVP deliverable)

```bash
python -m analysis.rankings results/<run>.csv
python -m analysis.coverage results/<run>.csv
```

**Expected outcome**: a per-task scores table + an overall **average-rank** table across the 3 frameworks and baselines, and a coverage table. This is the MVP: a defensible fair comparison.

**Validation checks (US1 / SC-002)**: in the CSV, confirm all runners on a given task share the same `metric`, `fold` count, and budget — i.e., identical protocol.

## Step 3 — Scale to the thesis run (Docker, 1 h, 10 folds)

```bash
bash automl-benchmark/scripts/run_full.sh        # runners × thesis × 1h, -m docker
```

Then regenerate every artifact:

```bash
python -m analysis.pareto            results/<run>.csv   # accuracy vs inference time
python -m analysis.by_characteristics results/<run>.csv  # ranking by size/dim/balance
```

**Expected outcome**: the rankings, coverage, Pareto, and by-characteristic tables/plots in `results/` — the inputs to `report/report.md`. Optionally re-run a subset at the `4h` budget to study the budget effect.

## Reproducibility (SC-004)

`scripts/run_full.sh` + the version-controlled `amlb_userdir/` + Docker images are the single documented path to regenerate the headline results from scratch in a clean environment.

## Maps to

US1 → Steps 1–2 · US2 (failures/coverage) → Step 2 coverage · US3 (Pareto) → Step 3 · US4 (by-characteristic) → Step 3 · US5 (reproducibility/report) → Reproducibility + `report/`.
