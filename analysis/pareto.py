"""Accuracy-vs-inference-time trade-off + Pareto frontier (FR-009, US3).

- **Accuracy axis** = average rank (1 = best), reused from ``analysis.rankings``. Ranks are
  comparable across task types, so we never compare incommensurable metrics directly (FR-008).
- **Time axis** = median ``predict_duration`` (seconds; lower is better).
- A framework is **Pareto-optimal** when no other framework is both at-least-as-accurate
  (rank) *and* at-least-as-fast, while being strictly better on at least one axis.

NOTE on the spec: tasks.md T020 phrased the accuracy axis as "median score". Median *raw*
score across mixed task types mixes auc / neg_logloss / neg_rmse scales — the exact pitfall
FR-008 exists to prevent — so we use average rank instead. Same intent, comparable units.
Filter to a single task type for a within-metric trade-off if desired.

CLI:  python -m analysis.pareto <results.csv>
"""
from __future__ import annotations
                        
import os
import sys

import pandas as pd

from analysis.load_results import load_results
from analysis.rankings import average_ranks


def _pareto_mask(rank, time):
    """Return a list[bool]: True where (rank, time) is Pareto-optimal (both lower = better)."""
    n = len(rank)
    optimal = [True] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dominates = (rank[j] <= rank[i] and time[j] <= time[i]
                         and (rank[j] < rank[i] or time[j] < time[i]))
            if dominates:
                optimal[i] = False
                break
    return optimal


def pareto_table(df):
    """Per-framework average rank vs median inference time, with a ``pareto`` flag.

    Columns: framework, avg_rank, predict_s, pareto. Sorted by predict_s (fastest first).
    """
    if "predict_duration" not in df.columns:
        raise ValueError("results missing 'predict_duration' (inference time) — cannot build Pareto")
    ok = df[df["success"]].copy()
    ok["predict_duration"] = pd.to_numeric(ok["predict_duration"], errors="coerce")
    median_time = ok.groupby("framework")["predict_duration"].median().rename("predict_s").reset_index()

    overall, _ = average_ranks(df)  # framework, avg_rank
    tbl = overall.merge(median_time, on="framework")
    tbl["pareto"] = _pareto_mask(tbl["avg_rank"].tolist(), tbl["predict_s"].tolist())
    return tbl.sort_values("predict_s").reset_index(drop=True)


def save_plot(tbl, path):
    """Write the trade-off scatter (Pareto-optimal points highlighted) to ``path``."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for _, r in tbl.iterrows():
        color = "#C9620A" if r["pareto"] else "#5C6B69"
        ax.scatter(r["predict_s"], r["avg_rank"], c=color, s=80, zorder=3)
        ax.annotate(r["framework"], (r["predict_s"], r["avg_rank"]),
                    fontsize=8, xytext=(6, 4), textcoords="offset points")
    frontier = tbl[tbl["pareto"]].sort_values("predict_s")
    ax.plot(frontier["predict_s"], frontier["avg_rank"], "--", color="#C9620A", lw=1, zorder=2)
    ax.set_xlabel("Median inference time (s) — lower is better")
    ax.set_ylabel("Average rank — lower is better")
    ax.invert_yaxis()
    ax.set_title("Accuracy vs inference-time trade-off (Pareto-optimal in amber)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.pareto <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    tbl = pareto_table(df)
    print("# Accuracy (avg rank, 1=best) vs inference time (median predict_duration, s)\n")
    print(tbl.to_string(index=False))
    out_dir = os.path.dirname(os.path.abspath(argv[1]))
    csv_path = os.path.join(out_dir, "pareto_table.csv")
    png_path = os.path.join(out_dir, "pareto.png")
    tbl.to_csv(csv_path, index=False)
    save_plot(tbl, png_path)
    print(f"\nwrote {csv_path}\nwrote {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
