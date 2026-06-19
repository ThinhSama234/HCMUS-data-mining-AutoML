"""Load and tidy an AMLB results CSV into a normalized dataframe.

Contract: ../specs/002-automl-benchmark/contracts/results-schema.md (FR-006/007/008).

The analysis layer never compares metrics across task types; this module just adds a
direction-normalized ``score`` (higher is always better) and a ``success`` flag so the
downstream ranking/coverage code stays simple.
"""
from __future__ import annotations

import pandas as pd

# AMLB's `result` column is ALREADY "higher is better": it reports auc, neg_logloss,
# neg_rmse, ... (research.md D5; verified against real output). So NO negation is needed
# for AMLB data. LOWER_IS_BETTER only kicks in for raw/bare metrics from other sources.
LOWER_IS_BETTER = {"logloss", "rmse", "mae", "mse", "rmsle"}
HIGHER_IS_BETTER = {"auc", "acc", "balacc", "bac", "f1", "r2", "pr_auc", "neg_logloss", "neg_rmse"}

REQUIRED_COLUMNS = ["framework", "task", "fold", "result"]


def _normalized_score(result, metric):
    """A score where higher is always better, or NA for a failed run."""
    if pd.isna(result):
        return pd.NA
    if metric in LOWER_IS_BETTER:
        return -float(result)
    return float(result)


def load_results(path):
    """Read an AMLB results CSV → tidy DataFrame with ``result_num``, ``success``, ``score``.

    Raises ValueError if the required columns are missing. Extra AMLB columns are kept.
    """
    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"results CSV missing required columns: {missing}")

    df["result_num"] = pd.to_numeric(df["result"], errors="coerce")
    # A run succeeded iff it produced a numeric result. Failures carry an empty result
    # plus an info/error message (never silently dropped — SC-001).
    df["success"] = df["result_num"].notna()

    has_metric = "metric" in df.columns

    def _score(row):
        metric = str(row["metric"]).lower() if has_metric else ""
        return _normalized_score(row["result_num"], metric)

    df["score"] = df.apply(_score, axis=1)
    return df
