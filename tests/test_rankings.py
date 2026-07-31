import os

import pandas as pd

from analysis.load_results import load_results
from analysis.rankings import average_ranks, mean_std_table, per_task_scores

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")


def test_best_framework_has_lowest_average_rank():
    df = load_results(FIXTURE)
    overall, _ = average_ranks(df)
    overall = overall.set_index("framework")
    assert overall.loc["AutoGluon", "avg_rank"] == 1.0          # wins all three tasks
    assert overall.loc["constantpredictor", "avg_rank"] == 3.5  # credit-g #4, vehicle #3


def test_ranks_do_not_mix_task_types():
    df = load_results(FIXTURE)
    _, by_type = average_ranks(df)
    assert {"binary", "multiclass", "regression"}.issubset(set(by_type["type"].unique()))


def test_per_task_scores_counts_completed_folds():
    df = load_results(FIXTURE)
    agg = per_task_scores(df)
    row = agg[(agg["framework"] == "AutoGluon") & (agg["task"] == "credit-g")]
    assert int(row["folds_completed"].iloc[0]) == 1


def _multifold():
    """A tiny 3-fold frame: framework A on one task across 3 folds with a known mean/std."""
    df = pd.DataFrame([
        ("t", "binary", "auc", "A", 0, 0.80),
        ("t", "binary", "auc", "A", 1, 0.90),
        ("t", "binary", "auc", "A", 2, 0.85),
    ], columns=["task", "type", "metric", "framework", "fold", "result_num"])
    df["success"] = True
    df["score"] = df["result_num"]
    return df


def test_per_task_scores_mean_std_over_folds():
    agg = per_task_scores(_multifold())
    r = agg.iloc[0]
    assert int(r["folds_completed"]) == 3
    assert abs(r["score_mean"] - 0.85) < 1e-9
    assert r["score_std"] > 0                              # 3 folds → real std


def test_mean_std_table_formats_mean_and_std():
    tbl = mean_std_table(_multifold())
    assert set(["framework", "score", "folds"]).issubset(tbl.columns)
    cell = tbl.iloc[0]["score"]
    assert "±" in cell and cell.startswith("0.8500")       # "0.8500 ± 0.0500"
    assert int(tbl.iloc[0]["folds"]) == 3


def test_mean_std_table_single_fold_shows_mean_only():
    tbl = mean_std_table(load_results(FIXTURE))            # fixture is single-fold
    assert (~tbl["score"].str.contains("±")).all()         # no ± when std is undefined
