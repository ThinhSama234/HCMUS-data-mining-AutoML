"""Jobs — monitor benchmark runs launched from Training.

Two modes on one page (like Methods):
  • LIST — every job as a clickable row → its detail (auto-refreshes while anything runs).
  • DETAIL (?job=<id>) — one job's status + failure reason, and a per-job dashboard (a scoped
    slice of the Evaluation view: per-dataset scores, train/predict time, and per-run failures).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import repo, runner  # noqa: E402

theme.inject()
_PILL = {"done": "ok", "running": "run", "failed": "fail", "queued": "queue", "cancelled": "queue"}

# completion toast for a job just launched from Training (st.session_state["_job"])
_w = st.session_state.get("_job")
if _w:
    _jw = runner.list_jobs()
    _rw = _jw[_jw["training_run_id"] == _w] if not _jw.empty else _jw
    if not _rw.empty and _rw.iloc[0]["status"] in ("done", "failed"):
        _s = _rw.iloc[0]["status"]
        st.toast(f"Job #{_w}: {_s}",
                 icon=":material/check_circle:" if _s == "done" else ":material/warning:")
        del st.session_state["_job"]


def _dur(a, b):
    """Compact duration between two timestamps (b−a); a is start, b is end-or-now."""
    if a is None or pd.isna(a) or b is None or pd.isna(b):
        return "—"
    s = int(max(0, (b - a).total_seconds()))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def _job_row(tr_id):
    """The one job's row from list_jobs(), or None."""
    df = runner.list_jobs()
    if df is None or df.empty:
        return None
    hit = df[df["training_run_id"] == tr_id]
    return hit.iloc[0] if not hit.empty else None


# ============================ DETAIL (?job=<id>) ============================
_sel = st.query_params.get("job")
if _sel is not None and _sel.isdigit():
    tr_id = int(_sel)

    def _detail():
        j = _job_row(tr_id)
        if j is None:
            theme.pagehead(f"Job #{tr_id}")
            st.markdown('<a href="?" target="_self" style="color:var(--teal);font-size:13px;'
                        'text-decoration:none">← All jobs</a>', unsafe_allow_html=True)
            st.warning("Job not found.")
            return
        status = j["status"]
        now = pd.Timestamp.now(tz="UTC")
        end = j["finished_at"] if not pd.isna(j["finished_at"]) else now
        theme.pagehead(f"Job #{tr_id} · {j.get('framework') or '—'}",
                       "Status and a per-job results dashboard.")
        st.markdown('<a href="?" target="_self" style="color:var(--teal);font-size:13px;'
                    'text-decoration:none">← All jobs</a>', unsafe_allow_html=True)

        # meta table
        _mono = lambda v: f'<span class="mono">{v}</span>'  # noqa: E731
        meta = [
            ("Framework", _mono(j.get("framework") or "—")),
            ("Constraint", _mono(j.get("constraint") or "—")),
            ("Status", theme.pill(status, _PILL.get(status, "queue"))),
            ("Datasets", _mono(int(j.get("datasets", 0)))),
            ("Runs", _mono(int(j.get("runs", 0)))),
            ("Started", _mono(str(j["started_at"])[:19] if not pd.isna(j["started_at"]) else "—")),
            ("Finished", _mono(str(j["finished_at"])[:19] if not pd.isna(j["finished_at"]) else "—")),
            ("Duration", _mono(_dur(j["started_at"], end))),
        ]
        theme.table(["Field", "Value"], [[f, v] for f, v in meta])

        # failure reason — the "why", surfaced plainly (not hidden)
        if status in ("failed", "cancelled") and j.get("error"):
            st.markdown(theme.status_note(
                "fail", f"This job {status}.", str(j["error"]),
                "See per-dataset failures below for which datasets failed and why."),
                unsafe_allow_html=True)

        # jump straight to the full Evaluation view, pre-filtered to this job's framework
        if j.get("framework"):
            if st.button(f"View {j['framework']}'s results in Evaluation",
                         icon=":material/leaderboard:"):
                st.session_state["eval_preset_fw"] = j["framework"]
                st.switch_page("views/evaluation.py")

        # per-job dashboard (a scoped slice of Evaluation)
        df = repo.load_job(tr_id)
        if df is None or df.empty:
            st.info("No runs recorded yet — results appear here as the job progresses."
                    if status in ("running", "queued") else
                    "This job has no per-run records linked to it. Use the button above to see this "
                    "framework's results in Evaluation.")
            return

        n_ok = int(df["success"].sum())
        mean_score = df.loc[df["success"], "score"].mean()
        theme.metric_cards([
            {"label": "Datasets", "value": f"{df['task'].nunique()}", "tone": "teal"},
            {"label": "Runs", "value": f"{len(df)}"},
            {"label": "Succeeded", "value": f"{n_ok}/{len(df)}",
             "note": f"{len(df) - n_ok} failed" if len(df) - n_ok else "all passed"},
            {"label": "Mean score", "value": f"{mean_score:.3f}" if pd.notna(mean_score) else "—",
             "tone": "amber", "note": "successful runs"},
        ])

        # score per dataset (only successful runs have a score)
        ok = df[df["success"] & df["score"].notna()]
        if not ok.empty:
            st.subheader("Score by dataset", help=(
                "This framework's score on each dataset (mean across folds). The metric depends on "
                "task type — AUC (binary), log-loss (multiclass), RMSE (regression)."))
            byds = ok.groupby("task", as_index=False)["score"].mean().sort_values("score")
            sfig = px.bar(byds, x="score", y="task", orientation="h",
                          color_discrete_sequence=[theme.TEAL],
                          labels={"score": "Score", "task": ""})
            sfig.update_layout(height=max(200, 30 * len(byds) + 60),
                               margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(sfig, width="stretch")

            # training vs predict time per dataset
            dur = ok.melt(id_vars="task", value_vars=["training_duration", "predict_duration"],
                          var_name="phase", value_name="seconds").dropna(subset=["seconds"])
            if not dur.empty:
                dur["phase"] = dur["phase"].map({"training_duration": "train",
                                                 "predict_duration": "predict"})
                st.subheader("Time by dataset", help="Wall-clock seconds to train and to predict.")
                tfig = px.bar(dur, x="seconds", y="task", color="phase", orientation="h",
                              barmode="group",
                              color_discrete_map={"train": theme.TEAL, "predict": theme.AMBER},
                              labels={"seconds": "Seconds", "task": "", "phase": ""})
                tfig.update_layout(height=max(220, 34 * dur["task"].nunique() + 60),
                                   margin=dict(l=0, r=0, t=10, b=0), legend_title_text="")
                st.plotly_chart(tfig, width="stretch")

        # per-run failures — dataset + the actual reason
        bad = df[~df["success"]]
        if not bad.empty:
            st.subheader(f"Failed runs ({len(bad)})", help=(
                "Runs excluded from the score. Each shows the dataset and the error the framework "
                "reported — the concrete reason it failed."))
            for _, r in bad.iterrows():
                with st.expander(f"{r.get('task') or '—'} — {r.get('status')}",
                                 icon=":material/warning:"):
                    st.code(str(r.get("info") or "no error message recorded"), language=None)

        if status == "running":
            st.caption("Auto-refreshing every 3s while this job runs.")

    if (_job_row(tr_id) is not None) and (_job_row(tr_id)["status"] == "running"):
        _detail = st.fragment(run_every="3s")(_detail)
    _detail()
    st.stop()


# ================================ LIST =====================================
theme.pagehead("Jobs", "Monitor benchmark runs — click a job for its status and dashboard.")


def _safe_jobs():
    """Returns (df, busy). Never raises — a bad read yields an empty frame, not a page crash."""
    try:
        runner.reap_stale_jobs()      # auto-fail 'running' jobs whose worker died without finishing
        df = runner.list_jobs()
        busy = (not df.empty) and bool((df["status"] == "running").any())
        return df, busy
    except Exception as e:                       # don't let one bad row nuke the whole page
        st.warning(f"Could not load jobs ({type(e).__name__}). Retrying on next refresh.")
        return None, True


_jobs0, _busy0 = _safe_jobs()

if _jobs0 is not None and _jobs0.empty:
    st.info("No runs yet — launch one on the **Training** page.")
    if st.button("Go to Training", icon=":material/play_arrow:", type="primary"):
        st.switch_page("views/training.py")
    st.stop()

# Stop controls live OUTSIDE the auto-refreshing fragment below: buttons inside a `run_every`
# fragment race the periodic rerun and silently drop clicks.
if _jobs0 is not None and not _jobs0.empty:
    for _, _j in _jobs0[_jobs0["status"] == "running"].iterrows():
        _jid = int(_j["training_run_id"])
        _sc = st.columns([4, 1])
        _sc[0].caption(f"Job #{_jid} · {_j.get('framework') or '—'} is running — Stop kills its "
                       "Docker container immediately.")
        if _sc[1].button("Stop", key=f"stop_{_jid}", icon=":material/stop:", width="stretch"):
            _stopped = runner.cancel(_jid)
            st.toast(f"Stopped job #{_jid}" if _stopped else f"Job #{_jid} already finished",
                     icon=":material/stop_circle:" if _stopped else ":material/info:")
            st.rerun()


@st.fragment(run_every=("3s" if _busy0 else None))
def _list():
    df, busy = _safe_jobs()
    if df is None or df.empty:
        return

    n = df["status"].value_counts()
    k = st.columns(3)
    k[0].metric("Running", int(n.get("running", 0)))
    k[1].metric("Done", int(n.get("done", 0)))
    k[2].metric("Failed", int(n.get("failed", 0)))

    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for _, j in df.iterrows():
        st_ = j["status"]
        jid = int(j["training_run_id"])
        end = j["finished_at"] if not pd.isna(j["finished_at"]) else now
        link = f'<a href="?job={jid}" target="_self" style="color:var(--teal);text-decoration:none">'
        rows.append([
            f'{link}<span class="mono">#{jid}</span></a>',
            f'<b>{j.get("framework") or "—"}</b>',
            j.get("constraint") or "—",
            theme.pill(st_, _PILL.get(st_, "queue")),
            f'{int(j.get("datasets", 0))}',
            f'{int(j["runs"])}',
            f'<span class="mono">{str(j["started_at"])[:19] if not pd.isna(j["started_at"]) else "—"}</span>',
            f'<span class="mono">{_dur(j["started_at"], end)}</span>',
            f'{link}Open ›</a>',
        ])
    theme.table(["Job", "Framework", "Constraint", "Status", "Datasets", "Runs", "Started",
                 "Duration", ""], rows)

    if busy:
        st.caption("Auto-refreshing every 3s while a job is running.")
    if _busy0 and not busy:
        st.rerun()


_list()
