"""US6 results explorer — headless tests of the pure data layer (SC-008, INV-1/INV-2).

These import the explorer's pure functions only (no Streamlit UI), so they run without a browser
and never start a server or a benchmark (INV-1). The console Evaluation page renders these exact
functions, so the page and the report can never disagree (INV-2).
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from analysis import explorer as app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(REPO_ROOT, "results", "results.csv")

pytestmark = pytest.mark.skipif(
    not os.path.exists(RESULTS), reason="no recorded results CSV to explore"
)


@pytest.fixture
def df():
    return app.load(RESULTS)


def test_filter_options_only_real_columns(df):
    opts = app.filter_options(df)
    assert set(opts) <= set(app.FILTER_COLUMNS)
    assert opts["framework"]  # at least one framework present


def test_apply_filters_subsets_and_empty_keeps_all(df):
    fw = app.filter_options(df)["framework"][0]
    only = app.apply_filters(df, {"framework": [fw]})
    assert set(only["framework"].unique()) == {fw}
    # empty selection is a no-op
    assert len(app.apply_filters(df, {"framework": []})) == len(df)


def test_ranking_view_reuses_analysis_module(df):
    per_task, overall, by_type = app.ranking_tables(df)
    assert {"framework", "avg_rank"} <= set(overall.columns)
    # INV-2: explorer numbers match running analysis.rankings directly
    from analysis import rankings
    ref_overall, _ = rankings.average_ranks(df)
    pd.testing.assert_frame_equal(
        overall.reset_index(drop=True), ref_overall.reset_index(drop=True)
    )


def test_pending_views_degrade_gracefully():
    # US3/US4 modules are optional → None when absent, so the page shows a "pending" notice
    # rather than crashing. When they exist, these return modules and the views light up.
    assert app.pareto_module() is None or hasattr(app.pareto_module(), "__name__")
    assert app.characteristics_module() is None or hasattr(app.characteristics_module(), "__name__")


def test_export_headline_figures(tmp_path, df):
    written = app.export_headline_figures(df, str(tmp_path))
    assert written and all(os.path.exists(p) for p in written)
