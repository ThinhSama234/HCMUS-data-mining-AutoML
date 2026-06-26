"""AutoML Bench Console — multipage entrypoint (st.navigation).

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

from console import onboarding, theme  # noqa: E402

st.set_page_config(page_title="AutoML Bench Console", page_icon="🧪", layout="wide")
theme.inject()

st.markdown(
    '<div style="font-weight:700;font-size:17px;letter-spacing:-.01em;">🧪 AutoML Bench Console</div>',
    unsafe_allow_html=True,
)

_PAGES = "views"
nav = st.navigation(
    {
        "Analyze": [st.Page(f"{_PAGES}/evaluation.py", title="Evaluation", icon="📊", default=True)],
        "Build": [
            st.Page(f"{_PAGES}/datasets.py", title="Datasets", icon="🗂"),
            st.Page(f"{_PAGES}/methods.py", title="Methods", icon="🧩"),
            st.Page(f"{_PAGES}/training.py", title="Training", icon="🚀"),
        ],
        "Operate": [
            st.Page(f"{_PAGES}/cost.py", title="Cost", icon="💰"),
            st.Page(f"{_PAGES}/deploy.py", title="Deploy", icon="🛰"),
        ],
    }
)
theme.sidebar_footer()
onboarding.maybe_show()   # one-time welcome dialog (first visit per session)
nav.run()
