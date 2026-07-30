"""Ranking-flip analysis — a lightweight, honest approximation of the AMLB Bradley-Terry tree.

The paper's most distinctive method is a Bradley-Terry *tree*: pairwise win/loss comparisons
between frameworks, recursively split by dataset characteristics to find where the relative
ranking *flips*. Full BT-tree partitioning needs R (`partykit`/`psychotree`); this module
delivers the same *insight* — "on group X framework A wins, on group Y framework B wins" — with
transparent pandas-only statistics and **no significance test** (labelled as an approximation).

Method (KISS):
1. Pairwise wins — per dataset, the framework with the higher mean `score` beats the other
   (ties split ½). Aggregate to a win-rate matrix W[a,b] and an overall win rate per framework.
2. Global order — frameworks by overall **average rank**, reused from `rankings.average_ranks`
   so this is the SAME ordering as the Overall leaderboard (never a contradictory "#1", INV-2).
3. Per-group order — the average-rank order within each tier of a characteristic
   (size/dim/balance/type), reusing the Phase-2 catalog characteristics — the same method the
   "Ranking by data characteristic" view already uses, so the flip section stays consistent.
4. Flip score — normalized Kendall-tau distance between each group's order and the global order,
   averaged over groups with enough data. The characteristic with the largest flip is the
   "best split" — the analogue of the BT tree's first split.

The pairwise **win matrix** is kept as the distinctive BT visualization (who beats whom across
datasets); the *ordering* used for flip detection is average-rank so it can never disagree with
the leaderboard the way a raw win-rate order can under unequal framework participation.

Small groups are guarded (`MIN_TASKS_PER_GROUP`): a group with too few datasets is skipped, and
if nothing splits we say so rather than inventing a flip. Stabilizes with the full suite.

CLI:  python -m analysis.ranking_flips <results.csv>
"""
from __future__ import annotations

import sys

import pandas as pd

from analysis.by_characteristics import with_characteristics
from analysis.load_results import load_results

CHARACTERISTICS = ["size_tier", "dim_tier", "balance_tier", "type"]
MIN_TASKS_PER_GROUP = 2   # a tier needs at least this many datasets to yield a trustworthy order


def _mean_scores(df):
    """Mean higher-is-better `score` per (task, framework) over completed folds."""
    empty = pd.DataFrame(columns=["task", "framework", "score"])
    if df.empty or "score" not in df.columns:
        return empty
    ok = df[df["success"].astype(bool)] if "success" in df.columns else df
    ok = ok[ok["score"].notna()]
    if ok.empty:
        return empty
    return ok.groupby(["task", "framework"])["score"].mean().reset_index()


def _pairwise(ms):
    """Accumulate wins/games per ordered framework pair from per-(task, framework) mean scores.

    Returns (wins, games, frameworks): dicts wins[a][b] / games[a][b] and the sorted framework list.
    A tie on a task contributes ½ a win to each side.
    """
    frameworks = sorted(ms["framework"].unique())
    wins = {a: {b: 0.0 for b in frameworks} for a in frameworks}
    games = {a: {b: 0 for b in frameworks} for a in frameworks}
    for _, g in ms.groupby("task"):
        sc = dict(zip(g["framework"], g["score"]))
        present = list(sc)
        for i, a in enumerate(present):
            for b in present[i + 1:]:
                games[a][b] += 1
                games[b][a] += 1
                if sc[a] > sc[b]:
                    wins[a][b] += 1
                elif sc[b] > sc[a]:
                    wins[b][a] += 1
                else:
                    wins[a][b] += 0.5
                    wins[b][a] += 0.5
    return wins, games, frameworks


def _avg_rank_order(df):
    """Frameworks best → worst by overall average rank (reused from `rankings.average_ranks`).

    This is the leaderboard ordering, so the flip section's global/per-group orders never
    contradict the Overall leaderboard (INV-2). Empty / no-success input → [].
    """
    if df.empty or "score" not in df.columns:
        return []
    ok = df[df["success"].astype(bool)] if "success" in df.columns else df
    if ok.empty or ok["score"].notna().sum() == 0:
        return []
    from analysis.rankings import average_ranks
    overall, _ = average_ranks(df)
    if overall.empty:
        return []
    return overall.sort_values("avg_rank", kind="stable")["framework"].tolist()


def win_matrix(df):
    """Pairwise win-rate matrix as a DataFrame (index=a, columns=b, value=P(a beats b)).

    Diagonal is NaN; a cell is NaN when the pair never met. Empty frame if no successful runs.
    """
    ms = _mean_scores(df)
    if ms.empty:
        return pd.DataFrame()
    wins, games, frameworks = _pairwise(ms)
    data = {}
    for a in frameworks:
        col = {}
        for b in frameworks:
            col[b] = float("nan") if a == b or games[a][b] == 0 else wins[a][b] / games[a][b]
        data[a] = col
    # rows = a, columns = b
    return pd.DataFrame(data).T.reindex(index=frameworks, columns=frameworks)


def global_order(df):
    """Frameworks best → worst by overall average rank (same ordering as the leaderboard)."""
    return _avg_rank_order(df)


def group_orders(df, by, meta=None):
    """`{tier: [frameworks best→worst]}` (average-rank order) per tier of characteristic `by`.

    Groups with fewer than ``MIN_TASKS_PER_GROUP`` scored datasets, or fewer than 2 rankable
    frameworks, are skipped.
    """
    if by not in CHARACTERISTICS:
        raise ValueError(f"unknown characteristic: {by}")
    cdf = with_characteristics(df, meta) if by != "type" else df.copy()
    if by not in cdf.columns:
        return {}
    orders = {}
    for tier, sub in cdf.groupby(by):
        ok = sub[sub["success"].astype(bool)] if "success" in sub.columns else sub
        if ok["task"].nunique() < MIN_TASKS_PER_GROUP:
            continue
        order = _avg_rank_order(sub)
        if len(order) >= 2:
            orders[str(tier)] = order
    return orders


def _kendall_frac(global_ord, group_ord):
    """Normalized Kendall-tau distance (fraction of discordant pairs) over common frameworks."""
    common = [f for f in global_ord if f in group_ord]
    n = len(common)
    if n < 2:
        return 0.0
    pos = {f: i for i, f in enumerate(group_ord)}
    seq = [pos[f] for f in common]              # group positions, in global order
    disc = sum(1 for i in range(n) for j in range(i + 1, n) if seq[i] > seq[j])
    return disc / (n * (n - 1) / 2)


def flip_scores(df, chars=None, meta=None):
    """Per-characteristic flip score: mean Kendall-tau distance of group orders vs the global order.

    Returns a DataFrame [characteristic, flip_score, n_groups] sorted by flip_score desc.
    A higher score means the ranking changes more across that characteristic's tiers.
    """
    chars = chars or CHARACTERISTICS
    g_order = global_order(df)
    rows = []
    for c in chars:
        try:
            gos = group_orders(df, c, meta)
        except ValueError:
            continue
        if not gos:
            continue
        fracs = [_kendall_frac(g_order, o) for o in gos.values()]
        rows.append({"characteristic": c,
                     "flip_score": sum(fracs) / len(fracs),
                     "n_groups": len(gos)})
    cols = ["characteristic", "flip_score", "n_groups"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values("flip_score", ascending=False).reset_index(drop=True)


def best_split(df, chars=None, meta=None):
    """The characteristic that most changes the ranking, with its per-group orders.

    Returns dict:
      {characteristic, flip_score, global_order, group_orders}  when a split with a flip exists,
      {characteristic: None, reason, global_order}              when there isn't enough data / no flip.
    """
    g_order = global_order(df)
    fs = flip_scores(df, chars, meta)
    top = fs[fs["flip_score"] > 0] if not fs.empty else fs
    if top.empty:
        reason = ("not enough data to split" if fs.empty
                  else "no ranking flip across any characteristic")
        return {"characteristic": None, "reason": reason, "global_order": g_order}
    row = top.iloc[0]
    c = row["characteristic"]
    return {"characteristic": c, "flip_score": float(row["flip_score"]),
            "global_order": g_order, "group_orders": group_orders(df, c, meta)}


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.ranking_flips <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    print("# Global pairwise win-rate order (best first)\n")
    print(" > ".join(global_order(df)) or "(no data)")
    print("\n# Flip score by characteristic (higher = ranking changes more)\n")
    print(flip_scores(df).to_string(index=False))
    bs = best_split(df)
    print("\n# Best split\n")
    if bs["characteristic"] is None:
        print(bs["reason"])
    else:
        print(f"{bs['characteristic']} (flip {bs['flip_score']:.2f})")
        for tier, order in bs["group_orders"].items():
            print(f"  {tier}: " + " > ".join(order))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
