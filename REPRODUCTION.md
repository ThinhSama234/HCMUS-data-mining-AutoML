# Reproduction Guide

End-to-end steps to reproduce the AutoML benchmark from scratch.

## Requirements

- Python 3.10+
- Java 8+ (only for H2O)
- Kaggle account + API credentials
- ~20 GB free disk space (framework venvs + datasets)

---

## Step 0 — Clone and install base deps

```bash
git clone <repo-url>
cd HCMUS-data-mining-AutoML

pip install pandas numpy scikit-learn openpyxl
```

---

## Step 1 — Set up Kaggle credentials

Download `kaggle.json` from https://kaggle.com → Account → API → Create New Token.

```bash
# Windows
mkdir %USERPROFILE%\.kaggle
copy kaggle.json %USERPROFILE%\.kaggle\kaggle.json

# Linux / Mac
mkdir ~/.kaggle
cp kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

---

## Step 2 — Download datasets

```bash
# Binary classification  (datasets support --unzip; competitions need manual unzip — see note below)
kaggle datasets    download -d blastchar/telco-customer-churn                   -p data/raw/telco_churn --unzip
kaggle datasets    download -d uciml/adult-census-income                        -p data/raw/adult_income --unzip
kaggle competitions download -c GiveMeSomeCredit                                -p data/raw/give_me_credit
kaggle competitions download -c santander-customer-satisfaction                  -p data/raw/santander_satisfaction

# Multiclass classification
kaggle datasets    download -d muratkokludataset/dry-bean-dataset                -p data/raw/dry_bean --unzip
kaggle datasets    download -d fatemehmehrparvar/obesity-levels                  -p data/raw/obesity --unzip
kaggle competitions download -c otto-group-product-classification-challenge      -p data/raw/otto_group
kaggle datasets    download -d uciml/forest-cover-type-dataset                  -p data/raw/forest_cover --unzip
kaggle datasets    download -d uciml/human-activity-recognition-with-smartphones -p data/raw/human_activity --unzip

# Regression
kaggle competitions download -c house-prices-advanced-regression-techniques      -p data/raw/house_prices
kaggle datasets    download -d rodolfomendes/abalone-dataset                     -p data/raw/abalone --unzip
kaggle datasets    download -d uciml/red-wine-quality-cortez-et-al-2009         -p data/raw/wine_quality --unzip
kaggle datasets    download -d vinayakshanawad/concrete-compressive-strength     -p data/raw/concrete --unzip
kaggle competitions download -c allstate-claims-severity                         -p data/raw/allstate_claims
```

Unzip competition downloads manually (PowerShell):

```powershell
foreach ($name in @("give_me_credit","santander_satisfaction","otto_group","house_prices","allstate_claims")) {
    $zip = Get-ChildItem "data\raw\$name\*.zip" | Select-Object -First 1
    Expand-Archive $zip.FullName -DestinationPath "data\raw\$name" -Force
}
```

> Note: competition datasets (give-me-some-credit, santander, otto, house-prices, allstate) require
> accepting the competition rules on Kaggle before the CLI download will work.

---

## Step 3 — Prepare datasets

Reads raw downloads, outputs `dataset/<name>/train.csv` + `meta.json`.

```bash
python scripts/prep.py --all
```

To check what files are expected per dataset:

```bash
python scripts/prep.py --list
```

---

## Step 4 — Generate shared k-fold indices

All frameworks use the same folds for a fair comparison.

```bash
python scripts/gen_folds.py
```

Default: 5-fold stratified CV, seed=42. To change:

```bash
python scripts/gen_folds.py --n-splits 10 --seed 0
```

---

## Step 5 — Create framework environments

One isolated venv per framework to avoid dependency conflicts.

```bash
# Windows
envs\setup.bat

# Skip H2O if Java is not installed
envs\setup.bat --skip h2o
```

This creates `envs/venvs/<framework>/` for each of:
`flaml`, `autogluon`, `h2o`, `lightautoml`, `mljar`, `baselines` (dummy + randomforest)

---

## Step 6 — Run the benchmark

```bash
# Full run (all frameworks × all datasets × all folds)
python scripts/orchestrator.py --time-budget 3600

# Smoke test — 60 seconds, flaml only, one dataset
python scripts/orchestrator.py --time-budget 60 --frameworks flaml --datasets telco_churn

# Resume a stopped run (pass the run ID printed at start)
python scripts/orchestrator.py --run-id 20260701_143022_abc123
```

Progress is saved after every fold — safe to Ctrl+C and resume anytime.

Report is written to `reports/run_<id>.json`.

---

## Step 7 — Analyse results

Open the notebook:

```bash
jupyter notebook notebooks/analysis.ipynb
```

Run all cells. The notebook:
- Loads all `reports/run_*.json` automatically
- Produces score comparison, heatmap, training time, score vs time, and ranking charts
- Reports mean ± std across folds per (dataset × framework)

---

## Directory layout after full run

```
dataset/
  telco_churn/      train.csv  meta.json  folds.json
  ...               (14 datasets total)

envs/
  venvs/
    flaml/          (isolated venv)
    autogluon/
    h2o/
    lightautoml/
    mljar/
    baselines/

reports/
  run_<id>.json     (one file per benchmark run)

notebooks/
  analysis.ipynb
```

---

## Reproducing exactly

To reproduce the exact numbers in the report:

- Use the same `--n-splits` and `--seed` in `gen_folds.py` (default: 5 splits, seed 42)
- Use the same `--time-budget` per fold
- Pin framework versions via `envs/requirements/*.txt` before running `setup.bat`
- Each `run_*.json` records `framework_version` per result entry for traceability

## Notebooks

Autogloun: https://colab.research.google.com/drive/1oR3wjd_NPxQasEq6xDVa8M-NOQ0zvHax#scrollTo=kKV7QtHBi-R4
H2O: https://colab.research.google.com/drive/1Pof72P20euFK19ONcoebyhBb9BQO3Hnt#scrollTo=i8f5odeFJpki