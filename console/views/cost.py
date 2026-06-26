"""Cost — estimate the compute cost of a benchmark run from the instance catalog × the budget.

Real estimator (no cloud needed): a constraint sets the time budget per (dataset × fold); the
total compute = datasets × frameworks × folds × budget, costed against each compute instance's
hourly rate. Upper bound — frameworks usually finish before exhausting the budget.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import repo, runner  # noqa: E402

theme.inject()
theme.pagehead("Cost", "Estimate the compute cost of a benchmark run")

inst = repo.list_instances()
if inst.empty:
    st.info("No compute instances in the catalog — run `python -m storage.seed`.")
    st.stop()

# sensible defaults from the live catalog
_runnable = sum(1 for d in runner.list_trainable_datasets() if d["runnable"]) or 1
_integrated = len(runner.list_runnable()) or 1
cons = runner.list_constraints() or [runner.DEFAULT_CONSTRAINT]
ci = cons.index(runner.DEFAULT_CONSTRAINT) if runner.DEFAULT_CONSTRAINT in cons else 0

st.subheader("Run to estimate")
c1, c2, c3 = st.columns(3)
con = c1.selectbox("Constraint", cons, index=ci,
                   help="Sets the time budget per dataset×fold (and the fold count).")
n_ds = c2.number_input("Datasets", 1, 200, value=_runnable,
                       help="How many datasets the run covers. Defaults to the trainable catalog.")
n_fw = c3.number_input("Frameworks", 1, 50, value=_integrated,
                       help="How many frameworks to run. Defaults to the integrated ones.")

info = runner.constraint_info(con) or {"folds": 1, "seconds": 60, "cores": 4}
folds, budget_s, cores = info["folds"] or 1, info["seconds"] or 0, info["cores"]
total_runs = int(n_ds) * int(n_fw) * int(folds)
compute_h = total_runs * budget_s / 3600.0

m = st.columns(3)
m[0].metric("Total runs", f"{total_runs:,}", help="datasets × frameworks × folds")
m[1].metric("Compute (worst case)", f"{compute_h:,.1f} h",
            help=f"{total_runs:,} runs × {budget_s}s budget. Upper bound — most runs finish early.")
m[2].metric("Budget / run", f"{budget_s}s", f"{folds} fold · {cores} cores")

st.subheader("Estimated cost by instance", help=(
    "Est. cost = compute hours × the instance's hourly rate. The rates are illustrative catalog "
    "defaults (not live cloud pricing), edit them in storage/seed.py. GPU rows multiply the SAME "
    "compute hours by a higher rate — no GPU speed-up is modelled, so they're only meaningful for "
    "GPU-capable frameworks; CPU-only ones (flaml, sklearn baselines) gain nothing from a GPU."))
rows = []
for _, r in inst.sort_values("rate_per_hour").iterrows():
    rate = float(r["rate_per_hour"] or 0)
    is_gpu = bool(r["gpu_type"])
    spec = f'{int(r["vcpus"])} vCPU · {int(r["memory_gb"])} GB' + (f' · {r["gpu_type"]}' if is_gpu else "")
    name = f'{r["name"]}' + (' <span class="note">⚠ no speed-up modelled</span>' if is_gpu else "")
    rows.append([f'<b>{name}</b>', f'<span class="mono">{spec}</span>',
                 f'<span class="mono">${rate:,.2f}/h</span>',
                 f'<span class="mono">${compute_h * rate:,.2f}</span>'])
theme.table(["Instance", "Spec", "Rate (illustrative)", "Est. cost"], rows)

st.markdown(
    '<div class="hint"><b>How to read this (not fake, but simplified):</b><br>'
    '• Formula is real: <span class="mono">cost = compute_hours × rate</span>, '
    '<span class="mono">compute_hours = datasets × frameworks × folds × budget</span>.<br>'
    '• <b>Rates are illustrative</b> defaults (≈ cloud tiers), not live pricing — edit in '
    '<span class="mono">storage/seed.py</span>.<br>'
    '• <b>Upper bound</b>: assumes every run uses its full budget, serially on one instance. '
    'Real cost is usually lower (early stopping) or faster wall-clock if parallelised.<br>'
    '• <b>GPU is not accelerated here</b> — GPU rows are just a higher rate over the same hours, '
    'so they only make sense for frameworks that actually use a GPU.</div>',
    unsafe_allow_html=True)
