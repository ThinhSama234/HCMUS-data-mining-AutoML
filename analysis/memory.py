"""Peak-memory analysis (report figure Hình 9).

The report pipeline records peak RAM per run in `resource_usage.peak_memory_mb`, which
`storage.ingest.ingest_report_json` stashes into the `runs.metrics` JSON (exposed by
`storage.repo.load` as the `metrics` column). This module pulls that value out and shapes it for
the Evaluation page: a per-(dataset × framework) matrix and a per-framework mean.

Memory is optional: AMLB smoke results carry only accuracy metrics (no `peak_memory_mb`), so every
helper degrades to an empty frame and the view info-degrades. Pure / UI-free (INV-1), read via the
tidy `repo.load()` frame so console and report never disagree (INV-2).

CLI:  python -m analysis.memory <results.csv>
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from analysis.load_results import load_results

_KEY = "peak_memory_mb"


def _peak(m):
    """Extract peak_memory_mb (float) from a metrics cell (dict / JSON string / None)."""
    if m is None or (isinstance(m, float) and pd.isna(m)):
        return None
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except (ValueError, TypeError):
            return None
    if isinstance(m, dict) and m.get(_KEY) is not None:
        try:
            return float(m[_KEY])
        except (TypeError, ValueError):
            return None
    return None


def memory_long(df):
    """Rows carrying peak memory: [task, framework, peak_memory_mb]. Empty if none recorded."""
    cols = ["task", "framework", _KEY]
    if df.empty or "metrics" not in df.columns:
        return pd.DataFrame(columns=cols)
    out = df.copy()
    out[_KEY] = out["metrics"].map(_peak)
    out = out[out[_KEY].notna() & out["framework"].notna() & out["task"].notna()]
    if out.empty:
        return pd.DataFrame(columns=cols)
    return out[cols].reset_index(drop=True)


def memory_matrix(df):
    """Mean peak memory per (framework × dataset) as a DataFrame (index=framework, columns=task).

    Empty frame if no memory was recorded (e.g. AMLB smoke results).
    """
    ml = memory_long(df)
    if ml.empty:
        return pd.DataFrame()
    return ml.pivot_table(index="framework", columns="task", values=_KEY, aggfunc="mean")


def memory_by_framework(df):
    """Mean peak memory per framework: [framework, mean_mb], highest first. Empty if none recorded."""
    ml = memory_long(df)
    if ml.empty:
        return pd.DataFrame(columns=["framework", "mean_mb"])
    return (ml.groupby("framework")[_KEY].mean().reset_index()
            .rename(columns={_KEY: "mean_mb"})
            .sort_values("mean_mb", ascending=False).reset_index(drop=True))


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.memory <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    by_fw = memory_by_framework(df)
    if by_fw.empty:
        print("# No peak_memory_mb recorded in these results.")
        return 0
    print("# Mean peak memory (MB) per framework\n")
    print(by_fw.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
