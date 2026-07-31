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
from storage import cost, repo, runner  # noqa: E402

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

est = cost.estimate(n_ds, n_fw, con)          # shared estimator (storage/cost.py) — also used by the API
folds, budget_s, cores = est["folds"], est["budget_seconds"], est["cores"]
total_runs, compute_h = est["total_runs"], est["compute_hours"]

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
for r in est["by_instance"]:                     # shared estimator (storage/cost.py) — no duplication
    rate, is_gpu = r["rate_per_hour"], bool(r["gpu_type"])
    spec = f'{r["vcpus"]} vCPU · {r["memory_gb"]} GB' + (f' · {r["gpu_type"]}' if is_gpu else "")
    name = f'{r["name"]}' + (' <span class="note">no GPU speed-up modelled</span>' if is_gpu else "")
    rows.append([f'<b>{name}</b>', f'<span class="mono">{spec}</span>',
                 f'<span class="mono">${rate:,.2f}/h</span>',
                 f'<span class="mono">${r["est_cost"]:,.2f}</span>'])
theme.table(["Instance", "Spec", "Rate (illustrative)", "Est. cost"], rows)

st.markdown(
    '<div class="hint"><b>How to read this</b><br>'
    '• <span class="mono">cost = compute_hours × rate</span>, '
    '<span class="mono">compute_hours = datasets × frameworks × folds × budget</span>.<br>'
    '• Rates are illustrative cloud-tier defaults — set in '
    '<span class="mono">storage/seed.py</span>.<br>'
    '• Upper bound: assumes every run uses its full budget, serially on one instance. '
    'Actual cost is usually lower with early stopping.<br>'
    '• GPU rows apply a higher rate over the same hours — meaningful only for GPU-capable '
    'frameworks.</div>',
    unsafe_allow_html=True)
