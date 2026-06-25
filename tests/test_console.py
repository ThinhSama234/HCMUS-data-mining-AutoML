"""Console (product-track prototype) — headless render tests for all 6 pages.

Uses Streamlit AppTest so each page is exercised without a browser/server. The Evaluation
page is live (reuses analysis.explorer); the rest are mock shells. All must render exception-free.
"""
from __future__ import annotations

import pytest

at = pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["evaluation", "datasets", "methods", "training", "cost", "deploy"]


def test_entrypoint_boots_default_page():
    app = AppTest.from_file("console/app.py", default_timeout=60).run()
    assert not app.exception
    # default page is Evaluation → a ranking chart + KPI metrics render
    assert len(app.get("metric") or []) == 4


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    app = AppTest.from_file(f"console/views/{page}.py", default_timeout=60).run()
    assert not app.exception, f"{page} raised: {[str(e) for e in app.exception]}"
