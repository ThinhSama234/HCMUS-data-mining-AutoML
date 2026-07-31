"""Statistical significance for the multi-framework comparison (evaluation-protocol §5).

The defensible way to compare several AutoML frameworks over many datasets (Demšar 2006):
1. **Friedman test** — is there any significant difference among frameworks at all?
2. **Nemenyi post-hoc** — which pairs differ; summarized by a **critical difference (CD)** and drawn
   as a CD diagram (average-rank axis; frameworks whose rank gap < CD are connected = not distinguishable).

Uses only `scipy` + `numpy` + `matplotlib` (already installed) — no `autorank`/`scikit-posthocs`
dependency. Pure / UI-free (INV-1); reads the tidy `repo.load()` frame (INV-2). Needs **complete
blocks** (frameworks scored on the same datasets), so it restricts to the common set and degrades to a
clear "insufficient data" result instead of raising.

CLI:  python -m analysis.significance <results.csv>
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

from analysis.load_results import load_results

MIN_FRAMEWORKS = 3   # Friedman/Nemenyi need ≥3 treatments to be meaningful
MIN_DATASETS = 3     # ...and ≥3 blocks


def score_matrix(df):
    """Datasets × frameworks matrix of mean higher-is-better `score`, restricted to complete blocks.

    Drops frameworks with no scores, then datasets missing any remaining framework — so every cell is
    filled (Friedman requires complete blocks). Empty frame if nothing usable.
    """
    if df.empty or not {"task", "framework", "score"}.issubset(df.columns):
        return pd.DataFrame()
    ok = df[df["success"].astype(bool)] if "success" in df.columns else df
    ok = ok[ok["score"].notna()]
    if ok.empty:
        return pd.DataFrame()
    mat = ok.pivot_table(index="task", columns="framework", values="score", aggfunc="mean")
    mat = mat.dropna(axis=1, how="all").dropna(axis=0, how="all")
    # Complete blocks: greedily drop the row (dataset) or column (framework) with the MOST missing
    # cells until no NaN remains — so one sparse framework drops that framework, and one sparse
    # dataset drops that dataset, instead of either collapsing the whole comparison.
    while not mat.empty and mat.isna().any().any():
        col_na, row_na = mat.isna().sum(axis=0), mat.isna().sum(axis=1)
        if col_na.max() >= row_na.max():           # tie → drop a framework column
            mat = mat.drop(columns=[col_na.idxmax()])
        else:
            mat = mat.drop(index=[row_na.idxmax()])
    return mat


def _as_matrix(df):
    """Accept either the tidy long results frame or an already-built datasets×frameworks matrix."""
    if isinstance(df, pd.DataFrame) and "framework" not in df.columns:
        return df
    return score_matrix(df)


def _avg_ranks(mat):
    """Average rank per framework (1 = best) over datasets; higher score → better rank."""
    ranks = mat.rank(axis=1, ascending=False, method="average")
    return ranks.mean(axis=0)   # Series indexed by framework


def friedman(df):
    """Friedman test across frameworks over datasets.

    Returns {significant, statistic, pvalue, n_datasets, n_frameworks, verdict} or a reason when there
    aren't enough complete blocks.
    """
    mat = _as_matrix(df)
    n_ds, n_fw = mat.shape if not mat.empty else (0, 0)
    if n_fw < MIN_FRAMEWORKS or n_ds < MIN_DATASETS:
        return {"significant": None,
                "reason": f"need ≥{MIN_FRAMEWORKS} frameworks and ≥{MIN_DATASETS} datasets with "
                          f"complete results (have {n_fw} frameworks × {n_ds} datasets)",
                "n_datasets": int(n_ds), "n_frameworks": int(n_fw)}
    import warnings

    from scipy.stats import friedmanchisquare
    with warnings.catch_warnings():           # a fully-degenerate (all-tied) input divides by zero
        warnings.simplefilter("ignore")
        stat, p = friedmanchisquare(*[mat[c].to_numpy() for c in mat.columns])
    if not (np.isfinite(stat) and np.isfinite(p)):   # undefined test → degrade, don't report p=nan
        return {"significant": None,
                "reason": "test undefined — no rank variation across frameworks (identical scores)",
                "n_datasets": int(n_ds), "n_frameworks": int(n_fw)}
    return {"significant": bool(p < 0.05), "statistic": float(stat), "pvalue": float(p),
            "n_datasets": int(n_ds), "n_frameworks": int(n_fw),
            "verdict": (f"Frameworks differ significantly (Friedman p={p:.4f})" if p < 0.05
                        else f"No significant difference among frameworks (Friedman p={p:.4f})")}


def critical_difference(df, alpha=0.05):
    """Nemenyi critical difference + average ranks.

    CD = q_alpha · sqrt(k(k+1)/(6N)), q_alpha = studentized-range critical value / √2 (Demšar 2006).
    Returns {cd, alpha, avg_ranks(dict), n_datasets, n_frameworks} or a reason if too few blocks.
    """
    mat = _as_matrix(df)
    n_ds, n_fw = mat.shape if not mat.empty else (0, 0)
    if n_fw < MIN_FRAMEWORKS or n_ds < MIN_DATASETS:
        return {"cd": None, "reason": "insufficient complete blocks",
                "n_datasets": int(n_ds), "n_frameworks": int(n_fw)}
    from scipy.stats import studentized_range
    q_alpha = studentized_range.ppf(1 - alpha, n_fw, np.inf) / math.sqrt(2)
    cd = float(q_alpha * math.sqrt(n_fw * (n_fw + 1) / (6.0 * n_ds)))
    ranks = _avg_ranks(mat).sort_values()
    return {"cd": cd, "alpha": alpha, "avg_ranks": ranks.to_dict(),
            "n_datasets": int(n_ds), "n_frameworks": int(n_fw)}


def nemenyi(df, alpha=0.05):
    """Pairwise Nemenyi: long df [a, b, rank_diff, significant] (|avg-rank gap| ≥ CD). Empty if too few blocks."""
    cd = critical_difference(df, alpha)
    cols = ["a", "b", "rank_diff", "significant"]
    if cd.get("cd") is None:
        return pd.DataFrame(columns=cols)
    ranks = cd["avg_ranks"]
    fws = list(ranks)
    rows = []
    for i, a in enumerate(fws):
        for b in fws[i + 1:]:
            diff = abs(ranks[a] - ranks[b])
            rows.append({"a": a, "b": b, "rank_diff": round(diff, 4),
                         "significant": bool(diff >= cd["cd"])})
    return pd.DataFrame(rows, columns=cols)


def cd_diagram(df, alpha=0.05):
    """A Demšar critical-difference diagram (matplotlib Figure), or None if too few complete blocks."""
    cd = critical_difference(df, alpha)
    if cd.get("cd") is None:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ranks = dict(sorted(cd["avg_ranks"].items(), key=lambda kv: kv[1]))
    names, values = list(ranks), list(ranks.values())
    k, cdv = len(names), cd["cd"]
    lo, hi = 1, k
    fig, ax = plt.subplots(figsize=(7, 1.2 + 0.35 * k))
    ax.set_xlim(lo - 0.5, hi + 0.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.hlines(0.85, lo, hi, color="#333")               # rank axis (best=1 on the left)
    for r in range(lo, hi + 1):
        ax.vlines(r, 0.83, 0.87, color="#333")
        ax.text(r, 0.90, str(r), ha="center", va="bottom", fontsize=8)
    # one labelled marker per framework, stacked down the left/right halves
    for idx, (name, val) in enumerate(zip(names, values)):
        y = 0.72 - idx * (0.62 / max(k - 1, 1))
        ax.plot([val, val], [0.85, y], color="#0C6E6A")
        side = lo - 0.4 if val <= (lo + hi) / 2 else hi + 0.4
        ha = "right" if side < val else "left"
        ax.plot([val, side], [y, y], color="#0C6E6A")
        ax.text(side + (-0.05 if ha == "right" else 0.05), y,
                f"{name} ({val:.2f})", ha=ha, va="center", fontsize=9)
    # CD bar
    ax.hlines(0.97, lo, lo + cdv, color="#C9620A", linewidth=3)
    ax.text(lo + cdv / 2, 0.99, f"CD = {cdv:.2f}", ha="center", va="bottom",
            fontsize=8, color="#C9620A")
    fig.tight_layout()
    return fig


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.significance <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    fr = friedman(df)
    print("# Friedman\n")
    print(fr.get("verdict") or fr.get("reason"))
    cd = critical_difference(df)
    if cd.get("cd") is not None:
        print(f"\n# Nemenyi CD = {cd['cd']:.3f} (alpha {cd['alpha']})  ranks (1=best):\n")
        for name, val in sorted(cd["avg_ranks"].items(), key=lambda kv: kv[1]):
            print(f"  {val:.2f}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
