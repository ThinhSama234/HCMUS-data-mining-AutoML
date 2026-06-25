"""Evaluation — LIVE page. The thesis results explorer (US6), reusing the tested analysis.explorer functions."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from analysis import explorer as expl  # noqa: E402 — reuse pure functions (single source of truth)
from console import state, theme  # noqa: E402

theme.inject()
theme.pagehead("Evaluation", "Benchmark results — from results.csv")

if not state.has_results():
    st.info("No results yet — run the benchmark first (quickstart Step 1).")
    st.stop()

df = state.load_results()
st.caption(f"data source: **{state.results_source()}** (SQLite cache if present, else results.csv)")

# Filters (mirror the mockup).
opts = expl.filter_options(df)
cols = st.columns(len(opts) or 1)
selected = {}
for c, (col, values) in zip(cols, opts.items()):
    selected[col] = c.multiselect(col.title(), values, default=[])
fdf = expl.apply_filters(df, selected)
if fdf.empty:
    st.warning("No rows match the current filters.")
    st.stop()

# KPI row.
per_task, overall, by_type = expl.ranking_tables(fdf)
best = overall.iloc[0]
k = st.columns(4)
k[0].metric("Best overall", str(best["framework"]), f"avg rank {best['avg_rank']:.2f}")
k[1].metric("Datasets", fdf["task"].nunique())
k[2].metric("Runs", len(fdf))
ok = int(fdf["success"].sum()) if "success" in fdf else len(fdf)
k[3].metric("Coverage", f"{100*ok//max(len(fdf),1)}%", f"{len(fdf)-ok} failures")

left, right = st.columns(2)
with left:
    st.subheader("Overall average rank")
    fig = px.bar(overall, x="avg_rank", y="framework", orientation="h",
                 labels={"avg_rank": "Average rank (1 = best)", "framework": ""},
                 color_discrete_sequence=[theme.TEAL])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Accuracy vs inference time")
    pareto = expl.pareto_module()
    if pareto is None:
        st.info("Pending **US3** — build `analysis/pareto.py` and this lights up "
                "(predict_duration already recorded).")
    else:
        ptbl = pareto.pareto_table(fdf)
        pfig = px.scatter(ptbl, x="predict_s", y="avg_rank", text="framework",
                          color="pareto", color_discrete_map={True: theme.AMBER, False: "#5C6B69"},
                          labels={"predict_s": "Median inference time (s)",
                                  "avg_rank": "Avg rank (1 = best)", "pareto": "Pareto-optimal"})
        pfig.update_traces(textposition="top center", marker=dict(size=13))
        pfig.update_yaxes(autorange="reversed")
        pfig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(pfig, use_container_width=True)

st.subheader("Ranking by data characteristic")
chars = expl.characteristics_module()
if chars is None:
    st.info("Pending **US4** — build `analysis/by_characteristics.py` and this lights up.")
else:
    by = st.selectbox("Group by", ["size_tier", "dim_tier", "balance_tier"])
    g = chars.grouped_rankings(fdf, by=by)
    cfig = px.bar(g, x="framework", y="avg_rank", color=by, barmode="group",
                  labels={"avg_rank": "Avg rank (1 = best)", "framework": ""})
    cfig.update_yaxes(autorange="reversed")
    cfig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(cfig, use_container_width=True)
    st.caption("One tier today (smoke = 3 small datasets); spread appears with the full suite.")

st.subheader("Average rank by task type")
st.dataframe(by_type, width="stretch", hide_index=True)
st.subheader("Per-task scores")
st.dataframe(per_task, width="stretch", hide_index=True)

if st.button("Export headline figures"):
    paths = expl.export_headline_figures(fdf, os.path.join(theme.REPO_ROOT, "results", "figures"))
    st.success("Wrote: " + ", ".join(os.path.relpath(p, theme.REPO_ROOT) for p in paths))
