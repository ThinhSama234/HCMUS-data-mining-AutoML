"""
Generate and save shared k-fold indices for all datasets.

Run once before any benchmark run. All frameworks use the same fold indices
so comparisons are fair (no split variance between frameworks).

Usage:
    python scripts/gen_folds.py
    python scripts/gen_folds.py --n-splits 10 --seed 42
    python scripts/gen_folds.py --force   # regenerate even if folds.json exists
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import KFold, StratifiedKFold

DATASET_DIR = Path("dataset")
N_SPLITS    = 5
SEED        = 42


def gen_folds(df: pd.DataFrame, label: str, task: str, n_splits: int, seed: int) -> list[dict]:
    y = df[label]
    idx = list(range(len(df)))

    if task == "classification":
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        splits   = splitter.split(idx, y)
    else:
        splitter = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
        splits   = splitter.split(idx)

    folds = []
    for train_idx, test_idx in splits:
        folds.append({
            "train": train_idx.tolist(),
            "test":  test_idx.tolist(),
        })
    return folds


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate shared k-fold indices")
    parser.add_argument("--n-splits", type=int, default=N_SPLITS)
    parser.add_argument("--seed",     type=int, default=SEED)
    parser.add_argument("--force",    action="store_true", help="Overwrite existing folds.json")
    args = parser.parse_args()

    found = 0
    for folder in sorted(DATASET_DIR.iterdir()):
        if not folder.is_dir():
            continue
        train_csv = folder / "train.csv"
        meta_json = folder / "meta.json"
        folds_out = folder / "folds.json"

        if not (train_csv.exists() and meta_json.exists()):
            continue

        if folds_out.exists() and not args.force:
            print(f"  skip  {folder.name}  (folds.json exists, use --force to regenerate)")
            continue

        meta  = json.loads(meta_json.read_text())
        df    = pd.read_csv(train_csv)
        label = meta["label"]
        task  = meta["task"]

        folds = gen_folds(df, label, task, args.n_splits, args.seed)

        payload = {
            "n_splits":  args.n_splits,
            "seed":      args.seed,
            "strategy":  "stratified" if task == "classification" else "kfold",
            "n_samples": len(df),
            "folds":     folds,
        }
        folds_out.write_text(json.dumps(payload, indent=2))

        sizes = [len(f["test"]) for f in folds]
        print(f"  wrote {folder.name}/folds.json  "
              f"({args.n_splits}-fold, test sizes: {sizes})")
        found += 1

    if found == 0 and not any(
        (d / "folds.json").exists()
        for d in DATASET_DIR.iterdir() if d.is_dir()
    ):
        print(f"No datasets found in {DATASET_DIR}/")
    else:
        print(f"\nDone. {found} dataset(s) written.")


if __name__ == "__main__":
    main()
