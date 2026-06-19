import os

from analysis.load_results import load_results

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")


def test_failed_run_flagged_not_dropped():
    df = load_results(FIXTURE)
    oom = df[(df["framework"] == "H2OAutoML") & (df["task"] == "big-imbalanced")]
    assert len(oom) == 1  # failure row present, not dropped (SC-001)
    assert bool(oom["success"].iloc[0]) is False


def test_successful_run_flagged():
    df = load_results(FIXTURE)
    row = df[(df["framework"] == "AutoGluon") & (df["task"] == "credit-g")]
    assert bool(row["success"].iloc[0]) is True


def test_result_is_already_higher_is_better():
    # AMLB reports auc / neg_logloss / neg_rmse, so a larger `result` is always better.
    df = load_results(FIXTURE)
    mb = df[(df["task"] == "Moneyball") & df["success"]].set_index("framework")
    assert mb.loc["AutoGluon", "score"] > mb.loc["H2OAutoML", "score"]  # neg_rmse -0.62 > -0.70
    cg = df[(df["task"] == "credit-g") & df["success"]].set_index("framework")
    assert cg.loc["AutoGluon", "score"] > cg.loc["flaml", "score"]  # auc 0.79 > 0.77
