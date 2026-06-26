"""Ranking grouped by dataset characteristics (FR-010, US4).

The AMLB results CSV does not carry dataset characteristics (n, p, class balance), so we
keep a small **curated, version-controlled** metadata table for the benchmark suite
(reproducible; mirrors the dataset catalog) and derive size / dimensionality / balance
tiers from it. `grouped_rankings` then reuses `analysis.rankings.average_ranks` within each
tier — so ranks stay comparable and we never mix metrics across task types (FR-008).

Tiers (size per data-model.md):
- size:    small <2,000 · medium 2,000–50,000 · large >50,000   (instances)
- dim:     low <20 · mid 20–100 · high >100                      (features)
- balance: imbalanced (binary minority <0.20) · balanced · n/a   (non-binary)

CLI:  python -m analysis.by_characteristics <results.csv>
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from analysis.load_results import load_results
from analysis.rankings import average_ranks

# task name -> (n_instances, n_features, minority_fraction | None for non-binary)
TASK_META = {
    "credit-g": (1000, 20, 0.30),
    "vehicle": (846, 18, None),       # multiclass
    "Moneyball": (1232, 14, None),    # regression
    "churn": (5000, 20, 0.14),
    "Higgs": (1_000_000, 28, 0.47),
}


def size_tier(n):
    if n is None:
        return "unknown"
    return "small" if n < 2_000 else "medium" if n < 50_000 else "large"


def dim_tier(p):
    if p is None:
        return "unknown"
    return "low" if p < 20 else "mid" if p <= 100 else "high"


def balance_tier(minority):
    if minority is None:
        return "n/a"
    return "imbalanced" if minority < 0.20 else "balanced"


def with_characteristics(df, meta=TASK_META):
    """Add size_tier / dim_tier / balance_tier columns derived from task metadata."""
    out = df.copy()

    def tiers(task):
        n, p, minority = meta.get(task, (None, None, None))
        return pd.Series({"size_tier": size_tier(n), "dim_tier": dim_tier(p),
                          "balance_tier": balance_tier(minority)})

    out[["size_tier", "dim_tier", "balance_tier"]] = out["task"].apply(tiers)
    return out


def grouped_rankings(df, by="size_tier", meta=TASK_META):
    """Average rank per framework within each group of `by`. Returns long df: [by, framework, avg_rank].

    `by` may be a derived tier (size_tier/dim_tier/balance_tier) or the raw `type` column
    (binary/multiclass/regression) — the latter folds the old "by task type" table into this view.
    """
    if by not in {"size_tier", "dim_tier", "balance_tier", "type"}:
        raise ValueError(f"unknown characteristic: {by}")
    cdf = with_characteristics(df, meta)
    frames = []
    for tier, sub in cdf.groupby(by):
        overall, _ = average_ranks(sub)
        overall[by] = tier
        frames.append(overall[[by, "framework", "avg_rank"]])
    if not frames:
        return pd.DataFrame(columns=[by, "framework", "avg_rank"])
    return pd.concat(frames, ignore_index=True).sort_values([by, "avg_rank"]).reset_index(drop=True)


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.by_characteristics <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    out_dir = os.path.dirname(os.path.abspath(argv[1]))
    for by in ("size_tier", "dim_tier", "balance_tier"):
        g = grouped_rankings(df, by=by)
        print(f"\n# Average rank by {by} (1 = best)\n")
        print(g.to_string(index=False))
        g.to_csv(os.path.join(out_dir, f"by_{by}.csv"), index=False)
    print(f"\nwrote by_*.csv to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
