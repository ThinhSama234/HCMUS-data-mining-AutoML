"""Overview (Home) — orientation landing: what's set up, the current best result, and the
guided next step. Answers "what's here / what's running / any results?" before the deep-dive pages.

Read-only summary over the same live data the other pages use (storage.repo + analysis.explorer);
every read is guarded so a fresh/empty install still renders a useful getting-started screen.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import onboarding, state, theme  # noqa: E402

theme.inject()
onboarding.maybe_show()   # first-visit welcome dialog — only on the Overview landing, once per session

# Branded hero — the one page that introduces the product before the working data.
st.markdown(
    '<div class="hero">'
    '<div class="hero-kicker">AutoML Benchmark Studio</div>'
    '<h1>AMLB Studio</h1>'
    '<p>Benchmark and compare AutoML frameworks on your own datasets — run them under identical '
    'time budgets, then explore who wins, where, and why. Everything below reflects your live '
    'catalog and results.</p>'
    '</div>',
    unsafe_allow_html=True,
)


def _safe(fn, default):
    """Never let one missing table blank the whole landing — fall back to a default."""
    try:
        return fn()
    except Exception:
        return default


# --- status: datasets · frameworks integrated · runs · best framework -------
from storage import repo, runner  # noqa: E402

_ds = _safe(repo.list_datasets, None)
n_ds = 0 if _ds is None or _ds.empty else len(_ds)

_methods = _safe(repo.list_methods, None)
n_methods = 0 if _methods is None or _methods.empty else len(_methods)
n_integrated = 0 if _methods is None or _methods.empty else \
    int((_methods["integration_status"] == "integrated").sum())

_jobs = _safe(lambda: runner.list_jobs(limit=100_000), None)   # count-all, not the default top-50
n_runs = 0 if _jobs is None or _jobs.empty else len(_jobs)

# best framework (lowest average rank) — only meaningful once results exist. Guarded like every
# other read on this page: a populated-but-degenerate results source must not crash the default
# landing page (honours the "every read is guarded" contract in the module docstring).
overall, best_name, best_note = None, None, None
if state.has_results():
    from analysis import explorer as expl
    overall = _safe(lambda: expl.ranking_tables(state.load_results())[1], None)
    if overall is not None and not overall.empty:
        b = overall.sort_values("avg_rank").iloc[0]
        best_name, best_note = str(b["framework"]), f"avg rank {b['avg_rank']:.2f}"

st.subheader("At a glance")
theme.metric_cards([
    {"label": "Datasets", "value": f"{n_ds}", "tone": "teal", "note": "in the catalog"},
    {"label": "Frameworks", "value": f"{n_integrated}/{n_methods}", "note": "integrated"},
    {"label": "Runs", "value": f"{n_runs}", "note": "benchmark jobs"},
    {"label": "Best framework", "value": best_name or "—", "tone": "amber",
     "note": best_note or "run a benchmark to see"},
])

# --- current standings (top 3), or a getting-started nudge ------------------
if best_name:
    st.subheader("Current standings", help=(
        "**Avg rank** = each framework's average finishing position across datasets (**1 = best**). "
        "On every dataset the frameworks are ranked by their score, then those ranks are averaged — "
        "so it's comparable across datasets even though the raw metric differs by task type "
        "(AUC for binary, log-loss for multiclass, RMSE for regression)."))
    rows = [[f'<span class="mono">#{i + 1}</span>', f"<b>{r['framework']}</b>",
             f'<span class="mono">{r["avg_rank"]:.2f}</span>']
            for i, (_, r) in enumerate(overall.sort_values("avg_rank").head(3).iterrows())]
    theme.table(["Rank", "Framework", "Avg rank (1 = best)"], rows)
else:
    st.markdown('<div class="hint">No results yet. Follow the steps below to run your first '
                'benchmark — results land on the <b>Evaluation</b> page.</div>',
                unsafe_allow_html=True)

# --- guided next steps ------------------------------------------------------
st.subheader("Next steps")
_STEPS = [
    ("views/datasets.py", "Add data", ":material/database:",
     "Upload a CSV, or pull from OpenML / Kaggle."),
    ("views/methods.py", "Integrate a framework", ":material/extension:",
     "Pull an AutoML framework's Docker image."),
    ("views/training.py", "Run a benchmark", ":material/play_circle:",
     "Launch an integrated framework on your datasets."),
    ("views/evaluation.py", "Analyze results", ":material/leaderboard:",
     "Leaderboard, Pareto, per-characteristic ranking."),
]
for col, (path, label, icon, desc) in zip(st.columns(len(_STEPS)), _STEPS):
    with col.container(border=True):
        if st.button(label, icon=icon, width="stretch", key=f"nav_{path}"):
            st.switch_page(path)
        st.caption(desc)
