"""Results-explorer pure data layer (US6, FR-016).

The read-only logic behind the console's **Evaluation** page: filter options, filtering, ranking
tables, optional-module discovery (US3 Pareto / US4 by-characteristic), and the static headline
figure export for the written report. UI-free and unit-tested so the Evaluation page and the
report can never disagree (INV-2), and so importing it never starts a server or a run (INV-1).

History: extracted from the former standalone ``dashboard/app.py`` (US6). The dashboard's Streamlit
UI was superseded by the console Evaluation page (``console/views/evaluation.py``), which is now the
single results UI; these functions are its — and the report's — shared engine. Contract:
``specs/002-automl-benchmark/contracts/dashboard-contract.md``.
"""
from __future__ import annotations

import importlib
import os

from analysis import rankings
from analysis.load_results import load_results

FILTER_COLUMNS = {
    "framework": "Framework",
    "type": "Task type",
    "task": "Dataset",
    "constraint": "Budget",
}


def load(path):
    """Load + tidy the results CSV via the shared loader. Raises on missing/bad file."""
    return load_results(path)


def filter_options(df):
    """Available filter values per column (only columns actually present)."""
    return {col: sorted(map(str, df[col].dropna().unique()))
            for col in FILTER_COLUMNS if col in df.columns}


def apply_filters(df, selected):
    """Subset df by the selected values. Empty/missing selection for a column = keep all."""
    out = df
    for col, values in selected.items():
        if values and col in out.columns:
            out = out[out[col].astype(str).isin([str(v) for v in values])]
    return out


def ranking_tables(df):
    """Reuse analysis.rankings — never recompute here (INV-2). Returns (per_task, overall, by_type)."""
    per_task = rankings.per_task_scores(df)
    overall, by_type = rankings.average_ranks(df)
    return per_task, overall, by_type


def _optional_module(name):
    """Import analysis.<name> if it exists yet (US3/US4), else None for graceful degrade."""
    try:
        return importlib.import_module(f"analysis.{name}")
    except ModuleNotFoundError:
        return None


def pareto_module():
    return _optional_module("pareto")


def characteristics_module():
    return _optional_module("by_characteristics")


def export_headline_figures(df, outdir):
    """Static export of the ranking figure (matplotlib) for the report (FR-016).

    Only exports views whose analysis module exists. Returns the list of written paths.
    """
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    written = []
    _, overall, _ = ranking_tables(df)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(overall["framework"], overall["avg_rank"], color="#0C6E6A")
    ax.set_xlabel("Average rank (1 = best)")
    ax.set_title("Overall average rank")
    ax.invert_yaxis()
    fig.tight_layout()
    path = os.path.join(outdir, "ranking_overall.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    written.append(path)
    return written
