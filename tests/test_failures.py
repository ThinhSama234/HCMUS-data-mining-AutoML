import os

from analysis.failures import (
    CATEGORIES,
    add_failure_category,
    by_category,
    by_framework,
    classify,
    failure_table,
)
from analysis.load_results import load_results

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_failures.csv")


# --- classify() unit tests: one per category ------------------------------------------

def test_classify_memory():
    assert classify("java.lang.OutOfMemoryError: GC overhead limit exceeded") == "memory"
    assert classify("Process killed (SIGKILL)") == "memory"


def test_classify_no_substring_false_positives():
    # Keywords must not match inside unrelated words (regression: "oom" ⊂ "mushroom"/"room").
    assert classify("No space left on device") != "memory"
    assert classify("mushroom cache overflow") != "memory"
    # A bare 'Killed' with no memory/timeout signal is a generic crash, not memory.
    assert classify("Killed") == "implementation"


def test_classify_time_from_message():
    assert classify("Timeout: time limit exceeded after 3600s") == "time"


def test_classify_time_from_duration_when_message_empty():
    # No message, but the run ran up to (≈) the budget → treated as a timeout.
    assert classify("", duration=3550, budget=3600) == "time"
    # Well under budget with no message stays unknown, not time.
    assert classify("", duration=5, budget=3600) == "unknown"


def test_classify_data_imbalance():
    # The Appendix D.1 case (yeast / wine-quality-white minority class).
    assert classify("ValueError: The least populated class in y has only 5 members") == "data"


def test_classify_implementation_is_the_catch_all_for_messages():
    assert classify("CalledProcessError: Command returned non-zero exit status 1") == "implementation"


def test_classify_unknown_when_no_signal():
    assert classify(None) == "unknown"
    assert classify(float("nan")) == "unknown"


# --- aggregation tests over the fixture -----------------------------------------------

def test_add_failure_category_excludes_successful_runs():
    df = load_results(FIXTURE)
    failed = add_failure_category(df)
    # 8 rows total, 1 is a successful AutoGluon run → 7 failures.
    assert len(failed) == 7
    assert "AutoGluon" not in set(failed["framework"])


def test_by_category_counts_all_five_categories():
    df = load_results(FIXTURE)
    cat = by_category(df).set_index("failure_category")["n"]
    assert list(by_category(df)["failure_category"]) == CATEGORIES  # stable order, zero-filled
    assert cat["memory"] == 1
    # 2 explicit timefw rows (1h + 4h) + silentfw (duration≈budget, no message) = 3.
    assert cat["time"] == 3
    assert cat["data"] == 1
    assert cat["implementation"] == 1
    assert cat["unknown"] == 1


def test_by_framework_is_grouped():
    df = load_results(FIXTURE)
    bf = by_framework(df)
    memrow = bf[(bf["framework"] == "memfw")]
    assert memrow["failure_category"].iloc[0] == "memory"
    assert int(memrow["n"].iloc[0]) == 1


def test_failure_table_keeps_budget_when_present():
    df = load_results(FIXTURE)
    tbl = failure_table(df)
    assert "constraint" in tbl.columns
    # timefw failed once per budget (1h and 4h).
    tf = tbl[tbl["framework"] == "timefw"]
    assert set(tf["constraint"]) == {"1h", "4h"}


def test_no_failures_degrades_gracefully():
    # A frame with only successful runs → empty failures, all-zero category table.
    df = load_results(os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv"))
    df_ok = df[df["success"]].copy()
    cat = by_category(df_ok)
    assert int(cat["n"].sum()) == 0
    assert list(cat["failure_category"]) == CATEGORIES


# --- Phase 6: failures by dataset-size tier (Hình 10 panel B) --------------------------

def test_by_size_groups_failures_by_size_tier():
    import pandas as pd

    from analysis.failures import by_size
    df = pd.DataFrame([
        ("bigds", "H2O", False, "out of memory"),
        ("smallds", "FLAML", False, "timeout"),
    ], columns=["task", "framework", "success", "info"])
    meta = {"bigds": (100_000, 10, None), "smallds": (500, 10, None)}   # injected catalog (offline)
    bs = by_size(df, meta=meta)
    assert set(bs.columns) == {"size_tier", "framework", "n"}
    assert {"large", "small"} <= set(bs["size_tier"])
    assert int(bs["n"].sum()) == 2
