"""Deploy — serve a trained model behind an endpoint. Placeholder (no backend yet)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402

theme.inject()
theme.pagehead("Deploy", "Serve a winning model behind an endpoint", live=False)
theme.coming_soon("Promote the best model from a benchmark run to a live endpoint, then "
                  "monitor its latency and status.")
