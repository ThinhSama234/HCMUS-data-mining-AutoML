"""Console (product-track prototype) — headless render tests for all 6 pages.

Uses Streamlit AppTest so each page is exercised without a browser/server. The Evaluation
page is live (reuses analysis.explorer); the rest are mock shells. All must render exception-free.
"""
from __future__ import annotations

import os

import pytest

at = pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["evaluation", "datasets", "methods", "training", "cost", "deploy"]
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")


def test_entrypoint_boots_default_page(tmp_path, monkeypatch):
    # Hermetic: seed a throwaway SQLite with known results so the Evaluation page
    # renders its 4 KPIs deterministically. Without this the test silently relied on
    # an ambient console.db (present on a dev machine, ABSENT on a clean CI checkout),
    # so it passed locally and failed in CI.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    from storage import db, migrate
    db._engine = None
    migrate.migrate(FIXTURE)

    app = AppTest.from_file("console/app.py", default_timeout=60).run()
    assert not app.exception
    # default page is Evaluation → KPI row renders exactly 4 metrics
    assert len(app.get("metric") or []) == 4

    db._engine = None


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    app = AppTest.from_file(f"console/views/{page}.py", default_timeout=60).run()
    assert not app.exception, f"{page} raised: {[str(e) for e in app.exception]}"
