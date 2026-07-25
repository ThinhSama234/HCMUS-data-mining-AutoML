"""
Dataset prep — reads raw Kaggle downloads, outputs train.csv + meta.json.

1. Download the raw files listed in DATASETS below (kaggle CLI or browser)
2. Place them in data/raw/<dataset_name>/
3. Run:
       python scripts/prep.py --dataset telco_churn
       python scripts/prep.py --all
       python scripts/prep.py --list      # show expected files per dataset
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW_BASE = Path("data/raw")
OUT_BASE = Path("dataset")

# registry: name → (kaggle_source, expected_raw_files, notes)
DATASETS = {
    # ── Binary Classification ──────────────────────────────────────────────
    "telco_churn": (
        "datasets/blastchar/telco-customer-churn",
        ["WA_Fn-UseC_-Telco-Customer-Churn.csv"],
        "Customer churn. AUC ~0.85. Mixed types.",
    ),
    "adult_income": (
        "datasets/uciml/adult-census-income",
        ["adult.csv"],
        "Income prediction. AUC ~0.93. Has '?' missing markers.",
    ),
    "give_me_credit": (
        "competitions/GiveMeSomeCredit",
        ["cs-training.csv"],
        "Credit default. AUC ~0.87. Missing values, imbalanced.",
    ),
    "santander_satisfaction": (
        "competitions/santander-customer-satisfaction",
        ["train.csv"],
        "370 anonymised features. AUC ~0.82. Hard.",
    ),
    # ── Multiclass Classification ──────────────────────────────────────────
    "dry_bean": (
        "datasets/muratkokludataset/dry-bean-dataset",
        ["Dry_Bean_Dataset.xlsx"],   # or .csv
        "7 bean classes. Overlapping clusters. log_loss ~0.07.",
    ),
    "obesity": (
        "datasets/fatemehmehrparvar/obesity-levels",
        ["ObesityDataSet_raw_and_data_sinthetic.csv"],
        "7 obesity levels. Mixed types.",
    ),
    "otto_group": (
        "competitions/otto-group-product-classification-challenge",
        ["train.csv"],
        "9 anonymised product classes. 93 features. log_loss ~0.46.",
    ),
    "forest_cover": (
        "datasets/uciml/forest-cover-type-dataset",
        ["covtype.csv"],
        "7 cover types. 581k rows. Large spread between models.",
    ),
    "human_activity": (
        "datasets/uciml/human-activity-recognition-with-smartphones",
        ["train/X_train.txt", "train/y_train.txt",
         "test/X_test.txt",  "test/y_test.txt", "features.txt"],
        "561 features. 6 activity classes. High-dim challenge.",
    ),
    # ── Regression ────────────────────────────────────────────────────────
    "house_prices": (
        "competitions/house-prices-advanced-regression-techniques",
        ["train.csv"],
        "79 features, many nulls & categoricals. High-dim regression.",
    ),
    "abalone": (
        "datasets/rodolfomendes/abalone-dataset",
        ["abalone.csv"],
        "Predict age from shell measurements. R² ~0.54. Genuinely hard.",
    ),
    "wine_quality": (
        "datasets/uciml/red-wine-quality-cortez-et-al-2009",
        ["winequality-red.csv"],
        "Predict wine quality score. R² ~0.36. Very noisy labels.",
    ),
    "concrete": (
        "datasets/vinayakshanawad/concrete-compressive-strength",
        ["compressive_strength.csv"],
        "Nonlinear regression. R² ~0.91. Good spread between models.",
    ),
    "allstate_claims": (
        "competitions/allstate-claims-severity",
        ["train.csv"],
        "Insurance loss severity. 124 features. Skewed target. Hard.",
    ),
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _save(name: str, df: pd.DataFrame, meta: dict) -> None:
    out = OUT_BASE / name
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "train.csv", index=False)
    meta_path = out / "meta.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"  wrote  meta.json")
    print(f"  wrote  {out}/train.csv  shape={df.shape}  label={meta['label']}")


def _find_csv(raw: Path) -> Path:
    candidates = sorted(raw.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV found in {raw}")
    return candidates[0]


# ── binary classification ─────────────────────────────────────────────────────

def prep_telco_churn(raw: Path) -> None:
    df = pd.read_csv(_find_csv(raw))
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["Churn"] = (df["Churn"] == "Yes").astype(int)
    _save("telco_churn", df, {
        "label": "Churn", "task": "classification", "metric": "auc",
        "drop_cols": ["customerID"],
    })


def prep_adult_income(raw: Path) -> None:
    df = pd.read_csv(_find_csv(raw))
    df.columns = df.columns.str.strip()
    income_col = next(c for c in df.columns if "income" in c.lower())
    df[income_col] = (df[income_col].str.strip()
                      .str.rstrip(".")
                      .map({"<=50K": 0, ">50K": 1}))
    df = df.rename(columns={income_col: "income"})
    df = df.replace("?", np.nan)
    _save("adult_income", df, {
        "label": "income", "task": "classification", "metric": "auc",
        "drop_cols": ["fnlwgt"],
    })


def prep_give_me_credit(raw: Path) -> None:
    df = pd.read_csv(raw / "cs-training.csv", index_col=0)
    _save("give_me_credit", df, {
        "label": "SeriousDlqin2yrs", "task": "classification", "metric": "auc",
        "drop_cols": [],
    })


def prep_santander_satisfaction(raw: Path) -> None:
    df = pd.read_csv(raw / "train.csv")
    _save("santander_satisfaction", df, {
        "label": "TARGET", "task": "classification", "metric": "auc",
        "drop_cols": ["ID"],
    })


# ── multiclass classification ─────────────────────────────────────────────────

def prep_dry_bean(raw: Path) -> None:
    xlsx = list(raw.glob("*.xlsx"))
    df   = pd.read_excel(xlsx[0]) if xlsx else pd.read_csv(_find_csv(raw))
    _save("dry_bean", df, {
        "label": "Class", "task": "classification", "metric": "log_loss",
        "drop_cols": [],
    })


def prep_obesity(raw: Path) -> None:
    df = pd.read_csv(_find_csv(raw))
    _save("obesity", df, {
        "label": "NObeyesdad", "task": "classification", "metric": "log_loss",
        "drop_cols": [],
    })


def prep_otto_group(raw: Path) -> None:
    df = pd.read_csv(raw / "train.csv")
    df["target"] = df["target"].str.replace("Class_", "").astype(int) - 1
    _save("otto_group", df, {
        "label": "target", "task": "classification", "metric": "log_loss",
        "drop_cols": ["id"],
    })


def prep_forest_cover(raw: Path) -> None:
    df = pd.read_csv(_find_csv(raw))
    label = "Cover_Type" if "Cover_Type" in df.columns else df.columns[-1]
    _save("forest_cover", df, {
        "label": label, "task": "classification", "metric": "log_loss",
        "drop_cols": [],
    })


def prep_human_activity(raw: Path) -> None:
    feat_names = (
        pd.read_csv(raw / "features.txt", header=None,
                    names=["idx", "name"], sep=r"\s+")["name"].tolist()
    )
    # deduplicate column names
    seen: dict[str, int] = {}
    clean: list[str] = []
    for n in feat_names:
        if n in seen:
            seen[n] += 1
            clean.append(f"{n}_{seen[n]}")
        else:
            seen[n] = 0
            clean.append(n)

    def _load(split: str) -> pd.DataFrame:
        X = pd.read_csv(raw / split / f"X_{split}.txt",
                        header=None, names=clean, sep=r"\s+")
        y = pd.read_csv(raw / split / f"y_{split}.txt",
                        header=None, names=["Activity"], sep=r"\s+")
        return pd.concat([X, y], axis=1)

    df = pd.concat([_load("train"), _load("test")], ignore_index=True)
    _save("human_activity", df, {
        "label": "Activity", "task": "classification", "metric": "log_loss",
        "drop_cols": [],
    })


# ── regression ────────────────────────────────────────────────────────────────

def prep_house_prices(raw: Path) -> None:
    df = pd.read_csv(raw / "train.csv")
    _save("house_prices", df, {
        "label": "SalePrice", "task": "regression", "metric": "rmse",
        "drop_cols": ["Id"],
    })


def prep_abalone(raw: Path) -> None:
    df = pd.read_csv(_find_csv(raw))
    # normalise label name across Kaggle variants
    rename = {c: "Rings" for c in df.columns
              if "ring" in c.lower() and c != "Rings"}
    if rename:
        df = df.rename(columns=rename)
    if "Rings" not in df.columns:
        df.columns = [*df.columns[:-1], "Rings"]
    _save("abalone", df, {
        "label": "Rings", "task": "regression", "metric": "rmse",
        "drop_cols": [],
    })


def prep_wine_quality(raw: Path) -> None:
    reds   = list(raw.glob("*red*.csv"))
    files  = reds if reds else sorted(raw.glob("*.csv"))
    # Kaggle version uses commas; original UCI uses semicolons — sniff automatically
    df     = pd.concat([pd.read_csv(f, sep=None, engine="python") for f in files], ignore_index=True)
    _save("wine_quality", df, {
        "label": "quality", "task": "regression", "metric": "rmse",
        "drop_cols": [],
    })


def prep_concrete(raw: Path) -> None:
    df = pd.read_csv(_find_csv(raw))
    target = next(
        (c for c in df.columns if "strength" in c.lower()
         or "csmpa" in c.lower().replace(" ", "")),
        df.columns[-1],
    )
    df = df.rename(columns={target: "strength"})
    _save("concrete", df, {
        "label": "strength", "task": "regression", "metric": "rmse",
        "drop_cols": [],
    })


def prep_allstate_claims(raw: Path) -> None:
    df = pd.read_csv(raw / "train.csv")
    _save("allstate_claims", df, {
        "label": "loss", "task": "regression", "metric": "rmse",
        "drop_cols": ["id"],
    })


# ── registry ──────────────────────────────────────────────────────────────────

HANDLERS: dict[str, callable] = {
    "telco_churn":              prep_telco_churn,
    "adult_income":             prep_adult_income,
    "give_me_credit":           prep_give_me_credit,
    "santander_satisfaction":   prep_santander_satisfaction,
    "dry_bean":                 prep_dry_bean,
    "obesity":                  prep_obesity,
    "otto_group":               prep_otto_group,
    "forest_cover":             prep_forest_cover,
    "human_activity":           prep_human_activity,
    "house_prices":             prep_house_prices,
    "abalone":                  prep_abalone,
    "wine_quality":             prep_wine_quality,
    "concrete":                 prep_concrete,
    "allstate_claims":          prep_allstate_claims,
}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Kaggle datasets")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dataset", choices=list(HANDLERS), help="Prep one dataset")
    grp.add_argument("--all",     action="store_true",    help="Prep all datasets")
    grp.add_argument("--list",    action="store_true",    help="List datasets and expected files")
    parser.add_argument("--raw-base", default=str(RAW_BASE),
                        help=f"Root folder for raw downloads (default: {RAW_BASE})")
    args = parser.parse_args()

    raw_base = Path(args.raw_base)

    if args.list:
        print(f"{'Dataset':<28} {'Kaggle source':<55} Expected files")
        print("─" * 120)
        for name, (slug, files, note) in DATASETS.items():
            print(f"  {name:<26} {slug:<55} {', '.join(files)}")
            print(f"  {'':26} {note}")
            print()
        return

    targets = list(HANDLERS) if args.all else [args.dataset]

    for name in targets:
        raw = raw_base / name
        print(f"\n── {name} {'─' * (50 - len(name))}")
        if not raw.exists():
            print(f"  [skip] {raw}/ not found — download first:")
            slug, files, _ = DATASETS[name]
            print(f"         kaggle {slug.split('/')[0][:-1] if '/' in slug else 'datasets'} download "
                  f"-{'c' if 'competitions' in slug else 'd'} "
                  f"{slug.split('/', 1)[-1]} -p {raw} --unzip")
            continue
        try:
            HANDLERS[name](raw)
        except Exception as e:
            print(f"  FAIL  {e}")


if __name__ == "__main__":
    main()
