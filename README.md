# AutoML Framework Benchmark (AMLB-style)

A reproducible, fair benchmark of three AutoML frameworks — **H2O AutoML, FLAML, AutoGluon** — plus baselines, on tabular OpenML tasks, following *AMLB: an AutoML Benchmark* (Gijsbers et al., JMLR 2024).

Spec & plan: [`specs/002-automl-benchmark/`](specs/002-automl-benchmark/).

## Approach

Reuse the official **`automlbenchmark` (AMLB)** tool as the harness (it enforces identical folds/budgets/metrics/resources and captures failures). This repo adds a thin **config layer** (`amlb_userdir/`), an **analysis layer** (`analysis/`), and the **report**.

## Layout

```
amlb_userdir/   config.yaml + benchmarks/ (datasets) + constraints.yaml (budgets)
scripts/        run_mvp.sh
analysis/       load_results.py, rankings.py (+ coverage/pareto/by_characteristics later)
tests/          unit tests + fixture for the analysis layer
results/        AMLB output CSVs + generated tables (gitignored)
report/         thesis writeup
```

## Prerequisites

- **Python 3.9–3.11** venv (not system Python).
- **Java** for H2O (present: openjdk 21).
- macOS local: **`brew install libomp`** (xgboost/FLAML need it).
- **H2O & AutoGluon don't install locally on macOS** — their setup scripts are Linux-first. Run those via **Docker** (`-m docker`, prebuilt Linux images) or a Linux/cloud box.

## Setup

```bash
cd automl-thesis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# AMLB tool — cloned OUTSIDE this repo to keep git clean:
git clone https://github.com/openml/automlbenchmark.git /Users/lap17650/workspace/automlbenchmark
pip install -r /Users/lap17650/workspace/automlbenchmark/requirements.txt
```

`amlb_userdir/config.yaml` (already present) is what makes `-u amlb_userdir` load our custom
`benchmarks/mvp.yaml` + `constraints.yaml`. Do **not** redefine a built-in framework
(e.g. `AutoGluon_bestquality`) in `frameworks.yaml` — AMLB errors on duplicate names.

## Run the MVP smoke

```bash
AMLB="python /Users/lap17650/workspace/automlbenchmark/runbenchmark.py"
# baselines + flaml run locally (after `brew install libomp`):
for fw in constantpredictor RandomForest flaml; do
  $AMLB $fw mvp smoke -m local -u amlb_userdir -o results -s force
done
# H2O + AutoGluon reliably via Docker (Linux images):
for fw in H2OAutoML AutoGluon; do
  $AMLB $fw mvp smoke -m docker -u amlb_userdir -o results -s force
done
python -m analysis.rankings results/results.csv   # ranking table
pytest                                             # validate analysis layer
```

## Status (last local run)

- ✅ Pipeline proven end-to-end: AMLB → `results.csv` → `analysis/` → ranking.
- ✅ MVP smoke ranking (local CPU, identical protocol): **flaml 1.33 > RandomForest 1.67 > constantpredictor 3.00**.
- ✅ 6/6 analysis unit tests pass.
- ⏳ H2O & AutoGluon: run via Docker/cloud (local macOS install fails — see `report/report.md`).

## Notes

- Baselines = three (`constantpredictor`, `RandomForest`, `TunedRandomForest`), per the paper. (Spec text says "two" — finding **F1**, reconcile before US5.) `TunedRandomForest` needs an older sklearn pin to run.
- Med-VQA constitution scoping = finding **D1**; fix via `/speckit-constitution` before US5.
- `results/_smoke_with_failures.csv` keeps the failure run — real data for the US2 failure-capture analysis.
