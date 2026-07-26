# =============================================================================
# NOTEBOOK B — H2O AutoML
# All 14 datasets × 5 folds × 1 framework
# Copy each CELL block into a separate Colab cell
# =============================================================================

# CELL 1 — Clone repo
# -----------------------------------------------------------------------------
import os
os.chdir('/content')
!rm -rf /content/repo
!git clone -b phat https://github.com/ptran1203/HCMUS-data-mining-AutoML /content/repo
os.chdir('/content/repo')
!pip install pandas numpy scikit-learn -q


# CELL 2 — Kaggle credentials
# -----------------------------------------------------------------------------
import json, os
from pathlib import Path

creds = {"username": "ptran1203", "key": "74cff31cf36a66ee4bda29f1f5712814"}
kdir  = Path.home() / ".kaggle"
kdir.mkdir(exist_ok=True)
(kdir / "kaggle.json").write_text(json.dumps(creds))
os.chmod(kdir / "kaggle.json", 0o600)
!pip install kaggle -q
print("Kaggle ready.")


# CELL 3 — Download all datasets
# -----------------------------------------------------------------------------
!kaggle datasets download -d blastchar/telco-customer-churn                    -p data/raw/telco_churn --unzip -q
!kaggle datasets download -d uciml/adult-census-income                         -p data/raw/adult_income --unzip -q
!kaggle datasets download -d muratkokludataset/dry-bean-dataset                 -p data/raw/dry_bean --unzip -q
!kaggle datasets download -d fatemehmehrparvar/obesity-levels                   -p data/raw/obesity --unzip -q
!kaggle datasets download -d uciml/forest-cover-type-dataset                   -p data/raw/forest_cover --unzip -q
!kaggle datasets download -d uciml/human-activity-recognition-with-smartphones  -p data/raw/human_activity --unzip -q
!kaggle datasets download -d rodolfomendes/abalone-dataset                      -p data/raw/abalone --unzip -q
!kaggle datasets download -d uciml/red-wine-quality-cortez-et-al-2009          -p data/raw/wine_quality --unzip -q
!kaggle datasets download -d vinayakshanawad/concrete-compressive-strength      -p data/raw/concrete --unzip -q

!kaggle competitions download -c GiveMeSomeCredit                               -p data/raw/give_me_credit -q
!kaggle competitions download -c santander-customer-satisfaction                 -p data/raw/santander_satisfaction -q
!kaggle competitions download -c otto-group-product-classification-challenge     -p data/raw/otto_group -q
!kaggle competitions download -c house-prices-advanced-regression-techniques     -p data/raw/house_prices -q
!kaggle competitions download -c allstate-claims-severity                        -p data/raw/allstate_claims -q

import zipfile, glob
for name in ["give_me_credit", "santander_satisfaction", "otto_group", "house_prices", "allstate_claims"]:
    for z in glob.glob(f"data/raw/{name}/*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(f"data/raw/{name}")
        os.remove(z)
        print(f"  unzipped {z}")

print("All datasets downloaded.")


# CELL 4 — Prepare datasets + generate folds
# -----------------------------------------------------------------------------
!python scripts/prep.py --all
!python scripts/gen_folds.py
print("Prep + folds done.")


# CELL 5 — Install H2O  (Java is pre-installed on Colab)
# -----------------------------------------------------------------------------
!pip install h2o -q
!java -version   # confirm Java is available
print("H2O installed.")


# CELL 6 — Run benchmark
# -----------------------------------------------------------------------------
!python scripts/orchestrator.py \
    --frameworks h2o \
    --time-budget 60 \
    --no-venv \
    --run-id run_h2o

print("Done.")


# CELL 7 — Download result
# -----------------------------------------------------------------------------
from google.colab import files
import glob
for f in glob.glob("reports/run_h2o*.json"):
    files.download(f)

# Option B: save to Google Drive
# from google.colab import drive
# drive.mount('/content/drive')
# !cp reports/run_h2o*.json /content/drive/MyDrive/automl_reports/
