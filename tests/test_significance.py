"""Phase 1 (evaluation-protocol) — Friedman + Nemenyi significance. Offline synthetic frames."""
import numpy as np
import pandas as pd

from analysis import significance as sig


def _frame(rows):
    """rows: (task, framework, score). Higher score = better."""
    df = pd.DataFrame(rows, columns=["task", "framework", "score"])
    df["success"] = True
    return df


def _dominant():
    """A strictly beats B beats C on every one of 6 datasets → a real, significant difference."""
    rows = []
    for i in range(6):
        rows += [(f"d{i}", "A", 0.90 + i * 0.001),
                 (f"d{i}", "B", 0.80 + i * 0.001),
                 (f"d{i}", "C", 0.70 + i * 0.001)]
    return _frame(rows)


def test_score_matrix_complete_blocks_only():
    df = _dominant()
    df = pd.concat([df, _frame([("d_extra", "A", 0.5)])])   # dataset missing B & C → dropped
    mat = sig.score_matrix(df)
    assert list(mat.columns) == ["A", "B", "C"] and "d_extra" not in mat.index
    assert mat.shape == (6, 3)


def test_friedman_detects_difference():
    fr = sig.friedman(_dominant())
    assert fr["significant"] is True and fr["pvalue"] < 0.05
    assert fr["n_frameworks"] == 3 and fr["n_datasets"] == 6


def test_friedman_null_not_significant():
    # rotate which framework wins each dataset so every framework averages rank 2 → no difference
    base, order, rows = [0.9, 0.8, 0.7], ["A", "B", "C"], []
    for i in range(6):
        rot = order[i % 3:] + order[:i % 3]      # cycle the winner; distinct scores (no ties)
        rows += [(f"d{i}", fw, sc) for fw, sc in zip(rot, base)]
    fr = sig.friedman(_frame(rows))
    assert fr["significant"] is False and fr["pvalue"] >= 0.05


def test_critical_difference_and_ranks():
    cd = sig.critical_difference(_dominant())
    assert cd["cd"] > 0
    ranks = cd["avg_ranks"]
    # A best (rank ~1), C worst (rank ~3)
    assert ranks["A"] < ranks["B"] < ranks["C"]
    assert abs(ranks["A"] - 1.0) < 1e-9 and abs(ranks["C"] - 3.0) < 1e-9


def test_nemenyi_flags_extreme_pair():
    ne = sig.nemenyi(_dominant())
    assert set(ne.columns) == {"a", "b", "rank_diff", "significant"}
    ac = ne[((ne["a"] == "A") & (ne["b"] == "C")) | ((ne["a"] == "C") & (ne["b"] == "A"))].iloc[0]
    assert bool(ac["significant"])            # A vs C: rank gap 2.0, well beyond CD for 3×6


def test_cd_diagram_returns_figure():
    fig = sig.cd_diagram(_dominant())
    assert fig is not None and hasattr(fig, "savefig")


def test_degrades_on_too_few_frameworks():
    df = _frame([("d0", "A", 0.9), ("d0", "B", 0.8),
                 ("d1", "A", 0.9), ("d1", "B", 0.8)])   # only 2 frameworks
    fr = sig.friedman(df)
    assert fr["significant"] is None and "reason" in fr
    assert sig.nemenyi(df).empty and sig.cd_diagram(df) is None


def test_all_tie_degrades_not_false():
    # every framework identical on every dataset → Friedman undefined (NaN); must degrade, NOT
    # be reported as a real "not significant" verdict with p=nan.
    rows = [(f"d{i}", fw, 0.8) for i in range(6) for fw in "ABC"]
    fr = sig.friedman(_frame(rows))
    assert fr["significant"] is None and "undefined" in fr["reason"]
    assert "pvalue" not in fr                       # no p=nan leaked


def test_sparse_framework_dropped_keeps_datasets():
    # A,B,C,D on all 6 datasets; E only on d0 → greedy drops the sparse framework E, keeps 6 datasets
    rows = [(f"d{i}", fw, 0.9 - "ABCD".index(fw) * 0.05) for i in range(6) for fw in "ABCD"]
    rows.append(("d0", "E", 0.5))
    mat = sig.score_matrix(_frame(rows))
    assert "E" not in mat.columns and mat.shape == (6, 4)   # dataset breadth preserved


def test_degrades_on_empty():
    empty = pd.DataFrame(columns=["task", "framework", "score", "success"])
    assert sig.score_matrix(empty).empty
    assert sig.friedman(empty)["significant"] is None
