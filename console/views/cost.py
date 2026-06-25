"""Cost — compute-instance catalog & cost estimator. Placeholder (no backend yet)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402

theme.inject()
theme.pagehead("Cost", "Compute pricing & per-run cost estimates", live=False)
theme.coming_soon("Pick a compute instance, estimate the cost of a benchmark run before "
                  "launching it, and track actual spend per job.")
