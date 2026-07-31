"""AMLB Studio — multipage console entrypoint (st.navigation).

Only sections backed by real data are shown (Evaluation / Datasets / Methods). Mock-only
sections (Training jobs, Compute pricing, Deploy) and the fake budget were removed — add them
back when they have a real backend.

Run:  streamlit run console/app.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402

st.set_page_config(page_title="AMLB Studio", page_icon=":material/analytics:", layout="wide")
theme.inject()

# No global wordmark in the main area — each page leads with its own title (theme.pagehead);
# the brand lives in the Overview hero and the sidebar footer.
_PAGES = "views"
nav = st.navigation(
    {
        "Home": [st.Page(f"{_PAGES}/overview.py", title="Overview",
                         icon=":material/home:", default=True)],
        # Setup = offline preparation (catalog data, integrate frameworks)
        "Setup": [
            st.Page(f"{_PAGES}/datasets.py", title="Datasets", icon=":material/database:"),
            st.Page(f"{_PAGES}/methods.py", title="Methods", icon=":material/extension:"),
        ],
        # Run = launch benchmark jobs and monitor them live
        "Run": [
            st.Page(f"{_PAGES}/training.py", title="Training", icon=":material/play_circle:"),
            st.Page(f"{_PAGES}/jobs.py", title="Jobs", icon=":material/monitoring:"),
        ],
        "Analyze": [st.Page(f"{_PAGES}/evaluation.py", title="Evaluation",
                            icon=":material/leaderboard:")],
        "Operate": [
            st.Page(f"{_PAGES}/cost.py", title="Cost", icon=":material/payments:"),
            st.Page(f"{_PAGES}/deploy.py", title="Deploy", icon=":material/rocket_launch:"),
        ],
    }
)
theme.sidebar_footer()
nav.run()   # the first-visit welcome dialog is shown by the Overview page, not globally
