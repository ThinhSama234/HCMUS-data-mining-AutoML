"""Evaluation — LIVE page. The thesis results explorer (US6), reusing the tested analysis.explorer functions."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from analysis import explorer as expl  # noqa: E402 — reuse pure functions (single source of truth)
from analysis import rankings  # noqa: E402 — mean±std table (Phase 2)
from console import state, theme  # noqa: E402
from storage import ingest  # noqa: E402 — report-JSON import bridge (Phase 4)

theme.inject()
theme.pagehead("Evaluation", "Benchmark results — from results.csv")

# Import / Export tucked into a small top-right "Data" popover — a secondary action, so the
# results (not the I/O plumbing) lead the page. Kept before the empty-state stop so import works
# even when there are no results yet.
_, _data_col = st.columns([5, 1])
with _data_col:
    with st.popover("Data", icon=":material/database:", width="stretch"):
        up = st.file_uploader("Import a run report (reports/run_*.json)", type=["json"],
                              help="Ingest results from the run_automl.py pipeline into the console.")
        if up is not None and st.button("Ingest report JSON", type="primary"):
            try:
                r = ingest.ingest_report_bytes(up.getvalue())
                st.success(f"Ingested {r['inserted']} run(s) — {r['datasets']} datasets, "
                           f"{r['methods']} frameworks, budget {r['constraint']}"
                           + (f"; {r['skipped_duplicate']} duplicate(s) skipped." if r['skipped_duplicate'] else "."))
                st.rerun()
            except Exception as exc:
                st.error(f"Import failed: {exc}")
        if state.has_results():
            st.download_button("Export results.csv",
                               state.load_results().to_csv(index=False).encode(),
                               file_name="results.csv", mime="text/csv")

if not state.has_results():
    st.info("No results yet — import a report (**Data** ▾, top-right), or run the benchmark "
            "(quickstart Step 1).")
    st.stop()

df = state.load_results()
st.caption(f"data source: **{state.results_source()}** (SQLite cache if present, else results.csv)")

# Filters (mirror the mockup). A framework can be pre-seeded when arriving from a job
# ("View <framework> in Evaluation" on the Jobs page) via session_state.
_preset_fw = st.session_state.pop("eval_preset_fw", None)
opts = expl.filter_options(df)
cols = st.columns(len(opts) or 1)
selected = {}
for c, (col, values) in zip(cols, opts.items()):
    if col == "framework":
        if _preset_fw is not None:                       # seed once, on arrival from a job
            st.session_state["flt_framework"] = [f for f in [_preset_fw] if f in values]
        selected[col] = c.multiselect(col.title(), values, key="flt_framework")
    else:
        selected[col] = c.multiselect(col.title(), values, default=[])
fdf = expl.apply_filters(df, selected)
if fdf.empty:
    st.warning("No rows match the current filters.")
    st.stop()

# KPI row.
per_task, overall, by_type = expl.ranking_tables(fdf)
best = overall.iloc[0]
k = st.columns(5)
ok = int(fdf["success"].sum()) if "success" in fdf else len(fdf)
k[0].metric("Best overall", str(best["framework"]), f"avg rank {best['avg_rank']:.2f}",
            help="The framework with the lowest average rank across all tasks "
                 "(per task, frameworks are ranked by score; 1 = best). The chip shows that mean rank.")
k[1].metric("Datasets", fdf["task"].nunique(),
            help="Number of distinct datasets/tasks in the current results.")
k[2].metric("Runs", len(fdf),
            help="Total result rows = framework × dataset × fold (each scored run).")
# how many folds each (dataset×framework) score averages — 1 = single split, >1 = k-fold CV
_folds = int(per_task["folds_completed"].median()) if not per_task.empty else 0
k[3].metric("Folds / result", _folds,
            help="Median number of CV folds each per-dataset score averages. 1 = single split; "
                 ">1 = k-fold cross-validation (report shows mean ± std over these folds).")
k[4].metric("Coverage", f"{100*ok//max(len(fdf),1)}%", f"{len(fdf)-ok} failures",
            help="Share of runs that finished successfully. The chip counts failed runs "
                 "(timeout / error / crash) — those are excluded from rankings.")

left, right = st.columns(2)
with left:
    st.subheader("Overall leaderboard", help=(
        "Frameworks ranked by mean finishing position across all tasks (per task ranked by score, "
        "1 = best, then averaged). Bars are a rank score = (N+1) − average rank, so the tallest bar "
        "on the left is #1. The label on each bar is the actual average rank."))
    ov = overall.sort_values("avg_rank").reset_index(drop=True)
    ov["place"] = [f'#{i + 1}  {fw}' for i, fw in enumerate(ov["framework"])]
    ov["rank_score"] = len(ov) + 1 - ov["avg_rank"]
    fig = px.bar(ov, x="place", y="rank_score", text="avg_rank",
                 category_orders={"place": ov["place"].tolist()},
                 color_discrete_sequence=[theme.TEAL], labels={"place": "", "rank_score": ""})
    fig.update_traces(texttemplate="avg rank %{text:.2f}", textposition="outside", cliponaxis=False)
    fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False,
                     range=[0, ov["rank_score"].max() + 0.6])
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, width="stretch")
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
        st.plotly_chart(pfig, width="stretch")

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
    st.plotly_chart(cfig, width="stretch")
    st.caption("Smoke run = 3 small datasets, so the spread is limited; it widens with the full suite.")

scores = expl.score_shapes_module()
if scores is not None:
    ns = scores.normalized_scores(fdf)
    if not ns.empty:
        st.subheader("Normalized performance", help=(
            "Each dataset's scores min-max normalized to [0,1] (1 = best framework on that "
            "dataset) so quality is comparable across datasets and metrics. Boxplot per framework, "
            "split by task type."))
        nfig = px.box(ns, x="framework", y="norm_score", color="framework", points="all",
                      facet_col="type" if "type" in ns.columns else None,
                      labels={"norm_score": "Normalized score (1 = best)", "framework": ""})
        nfig.update_layout(height=340, margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
        st.plotly_chart(nfig, width="stretch")

    sl = scores.score_long(fdf)
    if not sl.empty:
        st.subheader("Score distribution", help=(
            "Raw metric value per dataset across folds, grouped by task type — each cluster is a "
            "dataset, boxes are frameworks. Metric varies by task type (auc / logloss / rmse)."))
        sfig = px.box(sl, x="task", y="metric_value", color="framework",
                      facet_col="type" if "type" in sl.columns else None,
                      labels={"metric_value": "Metric value", "task": ""})
        sfig.update_xaxes(matches=None)
        sfig.update_yaxes(matches=None)
        sfig.update_layout(height=360, margin=dict(l=0, r=0, t=30, b=0), legend_title_text="")
        st.plotly_chart(sfig, width="stretch")

    svt = scores.score_vs_time(fdf)
    if not svt.empty:
        st.subheader("Score vs training time", help=(
            "Mean metric vs mean training time (log x), one panel per task type. A framework that "
            "is up/left is better and faster."))
        tfig = px.scatter(svt, x="mean_train_s", y="mean_score", color="framework", text="task",
                          facet_col="type" if "type" in svt.columns else None, log_x=True,
                          labels={"mean_train_s": "Mean training time (s, log)",
                                  "mean_score": "Mean metric"})
        tfig.update_traces(textposition="top center")
        tfig.update_xaxes(matches=None)
        tfig.update_yaxes(matches=None)
        tfig.update_layout(height=360, margin=dict(l=0, r=0, t=30, b=0), legend_title_text="")
        st.plotly_chart(tfig, width="stretch")

    inf = scores.inference_times(fdf)
    if not inf.empty:
        st.subheader("Inference time", help=(
            "Distribution of time to predict (seconds, log scale) per framework across folds."))
        ifig = px.box(inf, x="framework", y="predict_s", color="framework", points="all", log_y=True,
                      labels={"predict_s": "Inference time (s, log)", "framework": ""})
        ifig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(ifig, width="stretch")

    bp = scores.budget_performance(fdf)
    if not bp.empty:
        st.subheader("Performance by budget", help=(
            "Normalized performance (1 = best on the dataset) per framework at each time budget. "
            "A framework that keeps improving with a bigger budget rises across the bars."))
        n_budgets = bp["constraint"].nunique()
        bfig = px.bar(bp, x="framework", y="mean_norm", color="constraint", barmode="group",
                      labels={"mean_norm": "Mean normalized score", "framework": "",
                              "constraint": "Budget"})
        bfig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="Budget")
        st.plotly_chart(bfig, width="stretch")
        if n_budgets < 2:
            st.caption("Only one time budget in the current results — the budget comparison fills "
                       "in once runs at a second budget are ingested.")

    bu = scores.budget_usage(fdf)
    if not bu.empty:
        st.subheader("Budget usage (allocated vs actual)", help=(
            "Fairness check: every framework gets the **same** time budget; this shows how much of it "
            "each actually used (mean training time ÷ allocated budget). Bars near 100% ran to the "
            "limit; low bars finished early. Equal budgets = equal footing."))
        ufig = px.bar(bu, x="framework", y="pct_used",
                      color="constraint" if "constraint" in bu.columns else None,
                      labels={"pct_used": "% of time budget used", "framework": "",
                              "constraint": "Budget"})
        ufig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="Budget")
        st.plotly_chart(ufig, width="stretch")
        st.caption("Time budget + CPU cores are allocated **equally to every framework** by the AMLB "
                   "constraint (AMLB caps cores, not RAM); actual is measured wall-clock training time.")

memory = expl.memory_module()
if memory is not None:
    mbf = memory.memory_by_framework(fdf)
    if not mbf.empty:
        st.subheader("Memory usage", help=(
            "Peak memory (MB) recorded per run. Left: mean per framework. Right: per-(dataset × "
            "framework) heatmap. Only available for runs whose results carry peak_memory_mb."))
        ml, mr = st.columns(2)
        with ml:
            mfig = px.bar(mbf, x="mean_mb", y="framework", orientation="h",
                          color_discrete_sequence=[theme.TEAL],
                          labels={"mean_mb": "Mean peak memory (MB)", "framework": ""})
            mfig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(mfig, width="stretch")
        with mr:
            mat = memory.memory_matrix(fdf)
            if not mat.empty:
                hfig = px.imshow(mat, text_auto=".0f", aspect="auto",
                                 color_continuous_scale="Oranges",
                                 labels=dict(x="dataset", y="framework", color="MB"))
                hfig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(hfig, width="stretch")

st.subheader("Per-task scores (mean ± std)", help=(
    "Each framework's metric on each dataset as **mean ± std over the CV folds** (single split → just "
    "the mean). The `folds` column is how many folds were averaged. Metric varies by task type "
    "(auc / logloss / rmse)."))
st.dataframe(rankings.mean_std_table(fdf), width="stretch", hide_index=True)

st.subheader("Failure analysis", help=(
    "Failed runs are excluded from the rankings but not hidden (AMLB §6.4): a framework that "
    "silently drops the hard datasets can look artificially strong. Each failure is categorized "
    "from its error message — memory (OOM / segfault), time (budget exceeded), data (e.g. a "
    "minority class too small to fold), implementation (framework bug / crash), or unknown."))
failures = expl.failures_module()
if failures is None:
    st.info("Pending — build `analysis/failures.py` and this lights up.")
else:
    fcat = failures.by_category(fdf)
    if int(fcat["n"].sum()) == 0:
        st.success("No failed runs in the current selection.")
    else:
        _FAILCOLORS = {"memory": "#B5651D", "time": theme.AMBER, "data": "#7D6B9E",
                       "implementation": "#C0504D", "unknown": "#5C6B69"}
        fbf = failures.by_framework(fdf)
        if not fbf.empty:
            ffig = px.bar(fbf, x="framework", y="n", color="failure_category",
                          color_discrete_map=_FAILCOLORS,
                          category_orders={"failure_category": failures.CATEGORIES},
                          labels={"n": "Failed runs", "framework": "",
                                  "failure_category": "Category"})
            ffig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                               legend_title_text="")
            st.plotly_chart(ffig, width="stretch")
        # By-budget breakdown, when the results carry a budget/constraint column.
        ftbl = failures.failure_table(fdf)
        if "constraint" in ftbl.columns:
            st.caption("Failures by category and time budget")
            st.dataframe(ftbl, width="stretch", hide_index=True)
        # By dataset-size tier (Hình 10 panel B) — where the hard, large datasets fail.
        fbs = failures.by_size(fdf)
        if not fbs.empty and (set(fbs["size_tier"]) - {"unknown"}):
            st.caption("Failures by dataset size")
            bsfig = px.bar(fbs, x="size_tier", y="n", color="framework",
                           category_orders={"size_tier": ["small", "medium", "large", "unknown"]},
                           labels={"n": "Failed runs", "size_tier": "Dataset size"})
            bsfig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="")
            st.plotly_chart(bsfig, width="stretch")

st.subheader("Ranking-flip (Bradley-Terry approximation)", help=(
    "Where does the framework ranking change with data characteristics? Left: the pairwise "
    "win-rate matrix — P(row framework beats column framework) across datasets. Right: the "
    "characteristic that most flips the ranking, shown as global order vs per-group order. "
    "An honest approximation of the paper's Bradley-Terry trees — no significance test, no "
    "recursive partitioning."))
flips = expl.ranking_flips_module()
if flips is None:
    st.info("Pending — build `analysis/ranking_flips.py` and this lights up.")
else:
    wm = flips.win_matrix(fdf)
    if wm.empty or len(wm) < 2:
        st.info("Need at least two frameworks with results to compare pairwise.")
    else:
        fl, fr = st.columns(2)
        with fl:
            hfig = px.imshow(wm, text_auto=".2f", zmin=0, zmax=1,
                             color_continuous_scale="Teal",
                             labels=dict(x="loses to →", y="wins ↓", color="win rate"))
            hfig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(hfig, width="stretch")
        with fr:
            bs = flips.best_split(fdf)
            st.caption(f"Global order: **{' ▸ '.join(bs['global_order']) or '—'}**")
            if bs["characteristic"] is None:
                st.info(f"{bs['reason'].capitalize()} — stabilizes with the full suite.")
            else:
                st.caption(f"Biggest ranking flip: **{bs['characteristic']}** "
                           f"(flip score {bs['flip_score']:.2f})")
                rows = [{"group": g, "ranking": " ▸ ".join(o)}
                        for g, o in bs["group_orders"].items()]
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption("Approximation of Bradley-Terry trees (Strobl et al., 2011): the heatmap is "
               "pairwise win rates; the flip score is Kendall-tau between the leaderboard order "
               "and per-tier average-rank orders (tiers with <2 datasets are skipped, no "
               "significance test).")

st.subheader("Statistical significance", help=(
    "The rigorous multi-framework comparison (Demšar 2006): a **Friedman test** asks whether the "
    "frameworks differ at all; the **Nemenyi** post-hoc + **critical-difference (CD) diagram** show "
    "which differences are significant — frameworks joined within the CD are statistically "
    "indistinguishable. Needs several datasets with complete results."))
sig = expl.significance_module()
if sig is None:
    st.info("Pending — build `analysis/significance.py` and this lights up.")
else:
    fr = sig.friedman(fdf)
    if fr.get("significant") is None:
        st.info(f"Not enough data for a significance test — {fr['reason']}. "
                "Stabilizes with more datasets (see the dataset-suite expansion).")
    else:
        (st.success if fr["significant"] else st.warning)(
            f"{fr['verdict']} · {fr['n_frameworks']} frameworks × {fr['n_datasets']} datasets.")
        cdfig = sig.cd_diagram(fdf)
        if cdfig is not None:
            st.pyplot(cdfig)
        pairs = sig.nemenyi(fdf)
        if not pairs.empty:
            st.caption("Pairwise Nemenyi (significant = rank gap ≥ CD)")
            st.dataframe(pairs, width="stretch", hide_index=True)

if st.button("Export headline figures"):
    paths = expl.export_headline_figures(fdf, os.path.join(theme.REPO_ROOT, "results", "figures"))
    st.success("Wrote: " + ", ".join(os.path.relpath(p, theme.REPO_ROOT) for p in paths))
