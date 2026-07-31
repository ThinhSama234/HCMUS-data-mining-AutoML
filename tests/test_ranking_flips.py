"""Phase 3 — ranking-flip (Bradley-Terry approximation) tests.

Offline + deterministic: synthetic tidy frames (no DB), with an injected `meta` for tiers so
tier bucketing never touches the catalog. The headline case constructs a *known* flip — A wins
on small datasets, B wins on large — and asserts `best_split` finds the splitting characteristic.
"""
import pandas as pd

from analysis import ranking_flips as rf


def _rows(records):
    """Build a tidy results frame (success + numeric score) from (task, framework, score) tuples."""
    df = pd.DataFrame(records, columns=["task", "framework", "score"])
    df["success"] = True
    return df


# meta: 2 small datasets (n<2000) and 2 large (n>50000); features/minority irrelevant here.
_META = {"s1": (500, 10, None), "s2": (800, 10, None),
         "L1": (100_000, 10, None), "L2": (200_000, 10, None)}


def _flip_frame():
    # A beats B on the small datasets; B beats A on the large ones → ranking flips by size_tier.
    return _rows([
        ("s1", "A", 0.90), ("s1", "B", 0.80),
        ("s2", "A", 0.92), ("s2", "B", 0.85),
        ("L1", "A", 0.70), ("L1", "B", 0.88),
        ("L2", "A", 0.72), ("L2", "B", 0.90),
    ])


def test_win_matrix_shape_and_values():
    m = rf.win_matrix(_flip_frame())
    assert set(m.index) == {"A", "B"} and set(m.columns) == {"A", "B"}
    assert pd.isna(m.loc["A", "A"])                      # diagonal is NaN
    # A beats B on 2 of 4 datasets → 0.5 each way
    assert m.loc["A", "B"] == 0.5 and m.loc["B", "A"] == 0.5


def test_global_order_matches_average_ranks():
    from analysis.rankings import average_ranks
    # give A a clear overall edge so the order is unambiguous
    df = _rows([("t1", "A", 0.9), ("t1", "B", 0.5),
                ("t2", "A", 0.8), ("t2", "B", 0.6)])
    assert rf.global_order(df) == ["A", "B"]
    overall, _ = average_ranks(df)
    assert list(overall.sort_values("avg_rank")["framework"]) == rf.global_order(df)


def test_global_order_matches_leaderboard_under_unequal_participation():
    # Frameworks don't all run every dataset (the real multi-suite case). The flip section's
    # global order must equal the leaderboard's avg-rank order — no contradictory "#1" (INV-2).
    from analysis.rankings import average_ranks
    df = _rows([("t1", "A", 0.5), ("t1", "B", 0.8), ("t1", "C", 0.4),
                ("t2", "A", 0.6), ("t2", "B", 0.4),
                ("t3", "A", 0.5), ("t3", "B", 0.3), ("t3", "C", 0.8)])
    overall, _ = average_ranks(df)
    assert rf.global_order(df) == list(overall.sort_values("avg_rank", kind="stable")["framework"])


def test_best_split_finds_known_flip():
    bs = rf.best_split(_flip_frame(), meta=_META)
    assert bs["characteristic"] == "size_tier"          # the only characteristic that flips
    assert bs["flip_score"] > 0
    assert bs["group_orders"]["small"][0] == "A"        # A wins small
    assert bs["group_orders"]["large"][0] == "B"        # B wins large


def test_flip_scores_ranked_desc():
    fs = rf.flip_scores(_flip_frame(), meta=_META)
    assert list(fs["characteristic"])[0] == "size_tier"
    assert (fs["flip_score"].values[:-1] >= fs["flip_score"].values[1:]).all()


def test_no_flip_reports_insufficient_or_no_flip():
    # A dominates every dataset → no group can flip the order
    df = _rows([("s1", "A", 0.9), ("s1", "B", 0.5),
                ("L1", "A", 0.9), ("L1", "B", 0.5),
                ("L2", "A", 0.9), ("L2", "B", 0.5)])
    bs = rf.best_split(df, meta=_META)
    assert bs["characteristic"] is None and "reason" in bs
    assert bs["global_order"] == ["A", "B"]


def test_empty_results_degrade():
    empty = pd.DataFrame(columns=["task", "framework", "score", "success"])
    assert rf.global_order(empty) == []
    assert rf.win_matrix(empty).empty
    assert rf.best_split(empty, meta=_META)["characteristic"] is None
