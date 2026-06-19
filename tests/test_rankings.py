import os

from analysis.load_results import load_results
from analysis.rankings import average_ranks, per_task_scores

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
