"""Per-task scores and average-rank tables from AMLB results (FR-007, FR-008).

Ranks are computed WITHIN each task, so incommensurable metrics across task types are
never compared directly. The best framework on a task gets rank 1.

CLI:  python -m analysis.rankings <results.csv>
"""
from __future__ import annotations

import sys

from analysis.load_results import load_results


def per_task_scores(df):
    """Mean/std of the primary metric per (framework, task) over completed folds (FR-007)."""
    ok = df[df["success"]].copy()
    group_cols = [c for c in ["task", "type", "metric", "framework"] if c in ok.columns]
    return (
        ok.groupby(group_cols)["result_num"]
        .agg(score_mean="mean", score_std="std", folds_completed="count")
        .reset_index()
    )


def average_ranks(df):
    """Return (overall, by_type) average-rank tables. Rank 1 = best within a task."""
    ok = df[df["success"]].copy()
    has_type = "type" in ok.columns
    keys = ["task", "framework"] + (["type"] if has_type else [])

    mean_score = ok.groupby(keys)["score"].mean().reset_index()
    # rank frameworks within each task on the higher-is-better normalized score
    mean_score["rank"] = mean_score.groupby("task")["score"].rank(
        ascending=False, method="min"
    )

    overall = (
        mean_score.groupby("framework")["rank"]
        .mean()
        .sort_values()
        .reset_index()
        .rename(columns={"rank": "avg_rank"})
    )

    if has_type:
        by_type = (
            mean_score.groupby(["type", "framework"])["rank"]
            .mean()
            .reset_index()
            .rename(columns={"rank": "avg_rank"})
            .sort_values(["type", "avg_rank"])
        )
    else:
        by_type = overall.copy()

    return overall, by_type


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.rankings <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    print("# Per-task scores (mean +/- std over completed folds)\n")
    print(per_task_scores(df).to_string(index=False))
    overall, by_type = average_ranks(df)
    print("\n# Average rank by task type (1 = best)\n")
    print(by_type.to_string(index=False))
    print("\n# Overall average rank (1 = best)\n")
    print(overall.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
