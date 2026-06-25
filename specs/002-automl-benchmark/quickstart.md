# Quickstart: validate the benchmark end-to-end (MVP first)

Proves **User Story 1** (a fair head-to-head comparison) on 3 small datasets, then shows how to scale. This is a validation/run guide — implementation detail lives in `tasks.md` and the code.

## Prerequisites

- Linux with Python 3.9 (matches AMLB's pinned interpreter); GPU + CUDA for AutoGluon best-quality (optional for the smoke run).
- The `automlbenchmark` (AMLB) tool installed per its docs (clone + `pip install -r requirements.txt`, or the packaged CLI). Confirm the exact invocation at setup.
- This project's `amlb_userdir/` with `benchmarks/mvp.yaml` and `constraints.yaml` (see [benchmark-config-schema.md](./contracts/benchmark-config-schema.md)).

## Step 1 — MVP smoke run (local mode, ~10-min budget, 1 fold)

Run each framework + baseline on the MVP-3 datasets in local mode. Conceptually, for each runner in
`H2OAutoML flaml AutoGluon constantpredictor RandomForest TunedRandomForest`:

```bash
python runbenchmark.py <runner> mvp smoke -m local -u amlb_userdir
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
bash scripts/run_full.sh        # runners × thesis × 1h, -m docker
```

Then regenerate every artifact:

```bash
python -m analysis.pareto            results/<run>.csv   # accuracy vs inference time
python -m analysis.by_characteristics results/<run>.csv  # ranking by size/dim/balance
```

**Expected outcome**: the rankings, coverage, Pareto, and by-characteristic tables/plots in `results/` — the inputs to `report/report.md`. Optionally re-run a subset at the `4h` budget to study the budget effect.

## Reproducibility (SC-004)

`scripts/run_full.sh` + the version-controlled `amlb_userdir/` + Docker images are the single documented path to regenerate the headline results from scratch in a clean environment.

## Step 4 — Explore results in the interactive dashboard (US6)

The US6 explorer is the console's **Evaluation** page (it reuses the tested `analysis/explorer.py`
pure functions):

```bash
pip install streamlit plotly
streamlit run console/app.py        # Evaluation is the default page
```

**Expected outcome**: a browser app showing the ranking, accuracy/inference-time trade-off, and ranking-by-characteristic views, with filters for framework / task type / dataset / budget. See [dashboard-contract.md](./contracts/dashboard-contract.md). (The former standalone `dashboard/app.py` was consolidated into this page.)

**Validation checks (SC-008)**: the views render from the existing CSV alone; changing a filter updates every view; **no benchmark run is triggered** (INV-1); each shown number matches running the corresponding `analysis/*` module on the same CSV (INV-2). Headline figures export as static images for the report.

## Step 5 — Integrate a new framework with the skill (US7)

In Claude Code, run the skill against a Python, pip-installable framework that exposes `fit`/`predict`:

```text
/amlb-integrate-framework <pip-spec-or-name>
```

**Expected outcome**: a scaffolded `amlb_userdir/extensions/<Name>/` module (`__init__.py`, `exec.py`, `setup.sh`, `requirements.txt`) + a `amlb_userdir/frameworks.yaml` entry (`module: extensions.<Name>`), then a smoke-suite verification:

```bash
python runbenchmark.py <Name> mvp smoke -m local -u amlb_userdir
```

**Validation checks (SC-009)**: a conforming source produces a module that runs on the smoke suite and yields **scored predictions** (the harness scores, not the module); a non-conforming source (no installable package / no fit/predict) is **rejected with a stated reason and no partial module** is written. See [framework-integration-contract.md](./contracts/framework-integration-contract.md).

## Maps to

US1 → Steps 1–2 · US2 (failures/coverage) → Step 2 coverage · US3 (Pareto) → Step 3 · US4 (by-characteristic) → Step 3 · US5 (reproducibility/report) → Reproducibility + `report/` · US6 (dashboard) → Step 4 · US7 (integration skill) → Step 5.
