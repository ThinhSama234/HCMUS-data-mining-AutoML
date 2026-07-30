"""Phase 6 — peak-memory analysis (Hình 9). Offline, synthetic frames (no DB)."""
import json

import pandas as pd

from analysis import memory as mem


def _frame(records):
    """records: (task, framework, metrics) where metrics is a dict, JSON string, or None."""
    df = pd.DataFrame(records, columns=["task", "framework", "metrics"])
    df["success"] = True
    return df


def test_extracts_peak_from_dict_and_json_string():
    df = _frame([
        ("adult", "autogluon", {"peak_memory_mb": 357.0, "auc": 0.93}),
        ("adult", "h2o", json.dumps({"peak_memory_mb": 31.1})),      # JSON string form
        ("adult", "flaml", {"auc": 0.92}),                          # no memory key → dropped
    ])
    ml = mem.memory_long(df)
    assert set(ml["framework"]) == {"autogluon", "h2o"}
    assert ml.set_index("framework")["peak_memory_mb"]["autogluon"] == 357.0


def test_matrix_and_by_framework():
    df = _frame([
        ("adult", "A", {"peak_memory_mb": 100.0}),
        ("cal", "A", {"peak_memory_mb": 200.0}),
        ("adult", "B", {"peak_memory_mb": 40.0}),
    ])
    mat = mem.memory_matrix(df)
    assert mat.loc["A", "adult"] == 100.0 and mat.loc["A", "cal"] == 200.0
    byf = mem.memory_by_framework(df)
    # A mean = 150 > B mean = 40 → A first (highest)
    assert byf.iloc[0]["framework"] == "A" and byf.iloc[0]["mean_mb"] == 150.0


def test_degrades_when_no_memory_recorded():
    # AMLB-style metrics with no peak_memory_mb → empty (graceful), not a crash
    df = _frame([("t", "A", {"acc": 0.7, "auc": 0.5})])
    assert mem.memory_long(df).empty
    assert mem.memory_matrix(df).empty
    assert mem.memory_by_framework(df).empty


def test_degrades_when_metrics_column_absent():
    df = pd.DataFrame({"task": ["t"], "framework": ["A"], "success": [True]})
    assert mem.memory_long(df).empty
    assert mem.memory_matrix(df).empty
