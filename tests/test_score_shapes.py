"""Phase 5 — score-shaped view helpers (Hình 4/5/6/8). Offline, synthetic frames (no DB)."""
import numpy as np
import pandas as pd

from analysis import score_shapes as ss


def _frame(records):
    """Tidy results frame from (task, type, framework, fold, score, result_num, train_s, predict_s)."""
    df = pd.DataFrame(records, columns=["task", "type", "framework", "fold",
                                        "score", "result_num", "training_duration", "predict_duration"])
    df["success"] = True
    return df


def _sample():
    return _frame([
        ("adult", "binary", "A", 0, 0.90, 0.90, 100.0, 0.5),
        ("adult", "binary", "B", 0, 0.80, 0.80, 200.0, 0.2),
        ("cal", "regression", "A", 0, -0.40, -0.40, 120.0, 0.6),
        ("cal", "regression", "B", 0, -0.50, -0.50, 210.0, 0.3),
    ])


def test_normalized_scores_best_is_one_worst_is_zero():
    n = ss.normalized_scores(_sample())
    # per task the best framework = 1.0, the worst = 0.0
    adult = n[n["task"] == "adult"].set_index("framework")["norm_score"]
    assert adult["A"] == 1.0 and adult["B"] == 0.0
    cal = n[n["task"] == "cal"].set_index("framework")["norm_score"]
    assert cal["A"] == 1.0 and cal["B"] == 0.0          # -0.40 > -0.50 → A best
    assert set(n["norm_score"]) <= {0.0, 1.0}


def test_normalized_scores_all_equal_is_one():
    df = _frame([("t", "binary", "A", 0, 0.7, 0.7, 10.0, 0.1),
                 ("t", "binary", "B", 0, 0.7, 0.7, 10.0, 0.1)])
    n = ss.normalized_scores(df)
    assert (n["norm_score"] == 1.0).all()               # no spread → both best


def test_score_long_shape():
    sl = ss.score_long(_sample())
    assert list(sl.columns) == ["task", "type", "framework", "fold", "metric_value"]
    assert len(sl) == 4
    assert sl[sl["task"] == "cal"]["metric_value"].tolist() == [-0.40, -0.50]


def test_score_vs_time_aggregates():
    svt = ss.score_vs_time(_sample())
    assert {"framework", "task", "type", "mean_score", "mean_train_s"} <= set(svt.columns)
    row = svt[(svt["framework"] == "A") & (svt["task"] == "adult")].iloc[0]
    assert row["mean_score"] == 0.90 and row["mean_train_s"] == 100.0


def test_inference_times_and_missing_predict_degrades():
    inf = ss.inference_times(_sample())
    assert list(inf.columns) == ["framework", "predict_s"] and len(inf) == 4
    # report-sourced rows have no predict_duration → empty (graceful), not a crash
    no_predict = _sample().assign(predict_duration=np.nan)
    assert ss.inference_times(no_predict).empty


def test_null_task_type_kept_as_unknown_consistently():
    # a dataset with NULL task_type must appear in ALL score figures (as 'unknown'), not vanish
    # from some — the cross-figure inconsistency the reviewer flagged.
    df = _frame([("mystery", None, "A", 0, 0.9, 0.9, 50.0, 0.1),
                 ("mystery", None, "B", 0, 0.7, 0.7, 60.0, 0.2)])
    ns = ss.normalized_scores(df)
    svt = ss.score_vs_time(df)
    sl = ss.score_long(df)
    assert set(ns["type"]) == {"unknown"}
    assert set(svt["type"]) == {"unknown"}
    assert set(sl["type"]) == {"unknown"}
    assert "mystery" in set(ns["task"]) and "mystery" in set(svt["task"]) and "mystery" in set(sl["task"])


def test_budget_performance_normalizes_and_groups_by_budget():
    # same dataset at two budgets; A best at 60s, B catches up at 300s
    df = pd.DataFrame([
        ("adult", "binary", "A", 0, 0.90, 0.90, 60.0, 0.1, "60s"),
        ("adult", "binary", "B", 0, 0.70, 0.70, 60.0, 0.1, "60s"),
        ("adult", "binary", "A", 0, 0.92, 0.92, 300.0, 0.1, "300s"),
        ("adult", "binary", "B", 0, 0.95, 0.95, 300.0, 0.1, "300s"),
    ], columns=["task", "type", "framework", "fold", "score", "result_num",
                "training_duration", "predict_duration", "constraint"])
    df["success"] = True
    bp = ss.budget_performance(df)
    assert {"framework", "constraint", "mean_norm"} == set(bp.columns)
    assert set(bp["constraint"]) == {"60s", "300s"}
    # B is best overall (0.95) → norm 1.0 at 300s; worst overall (0.70) → 0.0 at 60s
    b = bp.set_index(["framework", "constraint"])["mean_norm"]
    assert b[("B", "300s")] == 1.0 and b[("B", "60s")] == 0.0


def test_budget_performance_degrades_without_constraint():
    df = pd.DataFrame({"task": ["t"], "framework": ["A"], "score": [0.9], "success": [True]})
    assert ss.budget_performance(df).empty


def test_budget_usage_allocated_vs_actual():
    df = pd.DataFrame([
        ("A", "60s", 30.0, 60.0),      # A uses 30 of 60s → 50%
        ("A", "60s", 30.0, 60.0),
        ("B", "60s", 6.0, 60.0),       # B finishes early → 10%
    ], columns=["framework", "constraint", "training_duration", "budget_s"])
    df["success"] = True
    bu = ss.budget_usage(df)
    assert {"framework", "constraint", "mean_train_s", "budget_s", "pct_used"} == set(bu.columns)
    assert bu.set_index("framework").loc["A", "pct_used"] == 50.0
    assert bu.set_index("framework").loc["B", "pct_used"] == 10.0


def test_budget_usage_degrades_without_budget_column():
    df = pd.DataFrame({"framework": ["A"], "training_duration": [30.0], "success": [True]})
    assert ss.budget_usage(df).empty        # no budget_s → empty, no crash


def test_all_helpers_degrade_on_empty():
    empty = pd.DataFrame(columns=["task", "type", "framework", "fold",
                                  "score", "result_num", "training_duration",
                                  "predict_duration", "success"])
    assert ss.normalized_scores(empty).empty
    assert ss.score_long(empty).empty
    assert ss.score_vs_time(empty).empty
    assert ss.inference_times(empty).empty
