"""Failure analysis — categorize failed AMLB runs (Memory / Time / Data / Implementation).

The AMLB paper (§6.4 + Appendix D) treats *failures* as a first-class result: a framework
that silently drops the hard datasets can look artificially strong, so failures must be
counted and explained, not hidden. `load_results` already flags a run as failed when it
produced no numeric result (`success == False`); those rows keep an ``info`` message. This
module classifies each failure into one of the paper's categories from that message (plus a
duration-vs-budget check for timeouts) and aggregates the counts for the Evaluation page.

Categories (paper §6.4):
- memory          — out-of-memory, segfault, SIGKILL/SIGSEGV.
- time            — exceeded the time budget (explicit message, or duration ≈ budget).
- data            — data-characteristic errors (e.g. a minority class too small to fold).
- implementation  — any other framework/code error (bug, traceback, subprocess crash).
- unknown         — failed with no message and no timeout signal.

Pure / UI-free (INV-1) and reused by the console via ``analysis.explorer`` (INV-2).

CLI:  python -m analysis.failures <results.csv>
"""
from __future__ import annotations

import sys

import pandas as pd

from analysis.load_results import load_results

CATEGORIES = ["memory", "time", "data", "implementation", "unknown"]

# Keyword tables (matched as substrings against the lowercased ``info`` message, in the
# order categories are checked below). Keep tokens long/specific enough to avoid matching
# inside unrelated words (e.g. never a bare "oom", which is a substring of "mushroom"/"room").
# Extend these as new framework error strings show up in the full-suite results.
MEMORY_KEYWORDS = (
    "out of memory", "outofmemory", "memoryerror", "oomkilled", "cannot allocate",
    "segmentation fault", "sigsegv", "sigkill",
)
TIME_KEYWORDS = (
    "timeout", "timed out", "time limit", "timelimit", "time_limit", "exceeded the time",
)
DATA_KEYWORDS = (
    "imbalanc", "minority", "only one class", "single class", "least populated class",
    "n_splits", "number of splits", "stratif", "n_samples", "too few",
)

# A run whose message is empty is treated as a timeout when its wall-clock reached this
# fraction of the budget (the paper allows a leniency period past the limit).
_TIME_BUDGET_FRACTION = 0.95


def _contains(text, keywords):
    return any(k in text for k in keywords)


def classify(info, duration=None, budget=None):
    """Classify a single failed run into one of ``CATEGORIES``.

    ``info`` is the AMLB message (may be NaN/empty). ``duration``/``budget`` (seconds) are
    optional and only used to catch silent timeouts when there is no message.
    """
    text = "" if info is None or (isinstance(info, float) and pd.isna(info)) else str(info).lower()

    if _contains(text, MEMORY_KEYWORDS):
        return "memory"
    if _contains(text, TIME_KEYWORDS):
        return "time"
    if not text and duration is not None and budget:
        try:
            if float(duration) >= float(budget) * _TIME_BUDGET_FRACTION:
                return "time"
        except (TypeError, ValueError):
            pass
    if _contains(text, DATA_KEYWORDS):
        return "data"
    if text:
        return "implementation"
    return "unknown"


def _budget_series(df):
    """Best-effort per-row time budget in seconds, or None if not derivable."""
    if "max_runtime_seconds" in df.columns:
        return pd.to_numeric(df["max_runtime_seconds"], errors="coerce")
    return None


def add_failure_category(df):
    """Return only the failed runs with a ``failure_category`` column added.

    Expects the ``success`` flag from ``load_results``. Missing ``info`` / ``duration`` /
    budget columns are tolerated (they just weaken timeout detection).
    """
    failed = df[~df["success"]].copy() if "success" in df.columns else df.copy()
    if failed.empty:
        failed["failure_category"] = pd.Series(dtype="object")
        return failed

    info = failed["info"] if "info" in failed.columns else pd.Series([None] * len(failed), index=failed.index)
    duration = pd.to_numeric(failed["duration"], errors="coerce") if "duration" in failed.columns else pd.Series([None] * len(failed), index=failed.index)
    budget = _budget_series(failed)
    if budget is None:
        budget = pd.Series([None] * len(failed), index=failed.index)

    failed["failure_category"] = [
        classify(i, d, b) for i, d, b in zip(info, duration, budget)
    ]
    return failed


def failure_table(df):
    """Long table of failure counts by the available grouping columns.

    Columns: [failure_category, framework?, constraint?, n]. ``framework`` / ``constraint``
    are included only when present in the input (the fixture, for example, has no budget).
    """
    failed = add_failure_category(df)
    group_cols = ["failure_category"] + [c for c in ("framework", "constraint") if c in failed.columns]
    if failed.empty:
        return pd.DataFrame(columns=group_cols + ["n"])
    return (
        failed.groupby(group_cols).size().rename("n").reset_index()
        .sort_values("n", ascending=False).reset_index(drop=True)
    )


def by_category(df):
    """Total failures per category (all categories present, zero-filled). Columns: [failure_category, n]."""
    failed = add_failure_category(df)
    counts = failed["failure_category"].value_counts() if not failed.empty else pd.Series(dtype=int)
    return (
        pd.DataFrame({"failure_category": CATEGORIES,
                      "n": [int(counts.get(c, 0)) for c in CATEGORIES]})
    )


def by_framework(df):
    """Failure counts per (framework, category). Columns: [framework, failure_category, n]."""
    failed = add_failure_category(df)
    if failed.empty or "framework" not in failed.columns:
        return pd.DataFrame(columns=["framework", "failure_category", "n"])
    return (
        failed.groupby(["framework", "failure_category"]).size().rename("n").reset_index()
        .sort_values(["framework", "n"], ascending=[True, False]).reset_index(drop=True)
    )


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.failures <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    n_fail = int((~df["success"]).sum()) if "success" in df.columns else 0
    print(f"# {n_fail} failed run(s) of {len(df)} total\n")
    print("## By category\n")
    print(by_category(df).to_string(index=False))
    print("\n## By framework\n")
    print(by_framework(df).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
