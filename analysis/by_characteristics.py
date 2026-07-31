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

# Curated baseline + offline fallback: task name -> (n_instances, n_features,
# minority_fraction | None for non-binary). The live catalog (load_task_meta) is the primary
# source; this covers the smoke tasks and any catalog row whose characteristics are still NULL.
TASK_META = {
    "credit-g": (1000, 20, 0.30),
    "vehicle": (846, 18, None),       # multiclass
    "Moneyball": (1232, 14, None),    # regression
    "churn": (5000, 20, 0.14),
    "Higgs": (1_000_000, 28, 0.47),
}


def _opt_num(v, cast):
    """Coerce a catalog value to int/float, or None (handles NaN / NULL / Decimal)."""
    if v is None or pd.isna(v):
        return None
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def load_task_meta(source=None):
    """`{task_name: (n_instances, n_features, minority_fraction)}` for tier derivation.

    Sourced from the dataset **catalog** (via ``storage.repo.list_datasets``) so the by-
    characteristic view scales to every ingested dataset — not the 5 hardcoded tasks. Catalog
    values are merged **over** the curated ``TASK_META`` baseline field-by-field, so a catalog
    row whose characteristics are still NULL keeps any curated value instead of going ``unknown``.

    Analysis stays decoupled from storage: the DB read is lazy, guarded, and optional — any
    failure (no DB, import error, empty catalog) falls back to ``TASK_META``. ``source`` is a
    test seam: a zero-arg callable returning a datasets-like DataFrame (columns
    ``name / n_instances / n_features / minority_fraction``).
    """
    meta = dict(TASK_META)
    try:
        if source is None:
            from storage import repo
            cat = repo.list_datasets()
        else:
            cat = source()
    except Exception:
        return meta
    if cat is None or getattr(cat, "empty", True):
        return meta
    for _, r in cat.iterrows():
        name = r.get("name")
        if name is None or pd.isna(name) or not str(name).strip():
            continue
        name = str(name)
        n = _opt_num(r.get("n_instances"), int)
        p = _opt_num(r.get("n_features"), int)
        minority = _opt_num(r.get("minority_fraction"), float)
        if n is None and p is None and minority is None:
            continue  # catalog knows nothing about this dataset → keep any curated baseline
        base = meta.get(str(name), (None, None, None))
        meta[str(name)] = (n if n is not None else base[0],
                           p if p is not None else base[1],
                           minority if minority is not None else base[2])
    return meta


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


def with_characteristics(df, meta=None):
    """Add size_tier / dim_tier / balance_tier columns derived from task metadata.

    ``meta`` defaults to the live catalog via ``load_task_meta()`` (resolved lazily so importing
    this module never touches the DB); pass an explicit dict to inject a fixed source in tests.
    """
    if meta is None:
        meta = load_task_meta()
    out = df.copy()

    def tiers(task):
        n, p, minority = meta.get(task, (None, None, None))
        return pd.Series({"size_tier": size_tier(n), "dim_tier": dim_tier(p),
                          "balance_tier": balance_tier(minority)})

    out[["size_tier", "dim_tier", "balance_tier"]] = out["task"].apply(tiers)
    return out


def grouped_rankings(df, by="size_tier", meta=None):
    """Average rank per framework within each group of `by`. Returns long df: [by, framework, avg_rank].

    `by` may be a derived tier (size_tier/dim_tier/balance_tier) or the raw `type` column
    (binary/multiclass/regression) — the latter folds the old "by task type" table into this view.
    `meta` defaults to the live catalog (see `with_characteristics`); pass a dict to inject in tests.
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
