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
ok = int(fdf["success"].sum()) if "success" in fdf else len(fdf)
k[0].metric("Best overall", str(best["framework"]), f"avg rank {best['avg_rank']:.2f}",
            help="The framework with the lowest average rank across all tasks "
                 "(per task, frameworks are ranked by score; 1 = best). The chip shows that mean rank.")
k[1].metric("Datasets", fdf["task"].nunique(),
            help="Number of distinct datasets/tasks in the current results.")
k[2].metric("Runs", len(fdf),
            help="Total result rows = framework × dataset × fold (each scored run).")
k[3].metric("Coverage", f"{100*ok//max(len(fdf),1)}%", f"{len(fdf)-ok} failures",
            help="Share of runs that finished successfully. The chip counts failed runs "
                 "(timeout / error / crash) — those are excluded from rankings.")

left, right = st.columns(2)
with left:
    st.subheader("Overall leaderboard", help=(
        "Frameworks ranked by mean finishing position across all tasks (per task ranked by score, "
        "1 = best, then averaged). Bars are a rank score = (N+1) − average rank, so the tallest bar "
        "on the left is #1. The label on each bar is the actual average rank."))
    ov = overall.sort_values("avg_rank").reset_index(drop=True)
    _MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}
    ov["place"] = [f'{_MEDAL.get(i + 1, f"#{i + 1}")} {fw}'
                   for i, fw in enumerate(ov["framework"])]
    ov["rank_score"] = len(ov) + 1 - ov["avg_rank"]
    fig = px.bar(ov, x="place", y="rank_score", text="avg_rank",
                 category_orders={"place": ov["place"].tolist()},
                 color_discrete_sequence=[theme.TEAL], labels={"place": "", "rank_score": ""})
    fig.update_traces(texttemplate="avg rank %{text:.2f}", textposition="outside", cliponaxis=False)
    fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False,
                     range=[0, ov["rank_score"].max() + 0.6])
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Accuracy vs inference time", help=(
        "Speed/quality trade-off: x = median time to predict, y = average rank (1 = best, top). "
        "Amber points are Pareto-optimal — no other framework is both faster and better-ranked."))
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

st.subheader("Ranking by data characteristic", help=(
    "Does a framework do better on certain kinds of data? Pick how to group the datasets "
    "(task type / size / #features / class balance). Within each group, frameworks are ranked by "
    "score per dataset and averaged, then shown as a rank score = (N+1) − average rank "
    "(N = frameworks in the group) — so a longer bar = better and the group's best scores N. "
    "‘unknown’ = datasets without curated size/feature metadata."))
chars = expl.characteristics_module()
if chars is None:
    st.info("Pending **US4** — build `analysis/by_characteristics.py` and this lights up.")
else:
    _CHAR = {"type": "Task type", "size_tier": "Dataset size",
             "dim_tier": "Number of features", "balance_tier": "Class balance"}
    _TIERS = {"type": "binary · multiclass · regression",
              "size_tier": "small &lt;2k · medium 2k–50k · large &gt;50k instances",
              "dim_tier": "low &lt;20 · mid 20–100 · high &gt;100 features",
              "balance_tier": "imbalanced (minority &lt;20%) · balanced · n/a (non-binary)"}
    by = st.selectbox("Group datasets by", list(_CHAR), format_func=lambda k: _CHAR[k])
    g = chars.grouped_rankings(fdf, by=by)
    # convert avg rank → rank score (higher = better) so bar length is monotone with quality
    g = g.assign(rank_score=g.groupby(by)["framework"].transform("count") + 1 - g["avg_rank"])
    # best (highest mean score) at the top: list ascending so plotly draws it last (topmost)
    order = g.groupby("framework")["rank_score"].mean().sort_values().index.tolist()
    cfig = px.bar(g, x="rank_score", y="framework", color=by, barmode="group", orientation="h",
                  text="rank_score", category_orders={"framework": order},
                  labels={"rank_score": "Rank score (higher = better)", "framework": "", by: _CHAR[by]})
    cfig.update_traces(texttemplate="%{x:.1f}", textposition="outside", cliponaxis=False)
    cfig.update_xaxes(dtick=1, range=[0, g["rank_score"].max() + 0.7])
    cfig.update_layout(height=max(220, 70 * g["framework"].nunique() + 60),
                       margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(cfig, use_container_width=True)
    st.caption("Smoke run = 3 small datasets, so the spread is limited; it widens with the full suite.")

st.subheader("Per-task scores", help=(
    "The raw score of every framework on every dataset (and fold) — the underlying numbers the "
    "ranks above are computed from. Metric varies by task type (auc / logloss / rmse)."))
st.dataframe(per_task, width="stretch", hide_index=True)

if st.button("Export headline figures"):
    paths = expl.export_headline_figures(fdf, os.path.join(theme.REPO_ROOT, "results", "figures"))
    st.success("Wrote: " + ", ".join(os.path.relpath(p, theme.REPO_ROOT) for p in paths))
