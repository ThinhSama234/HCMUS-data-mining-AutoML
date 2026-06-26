"""Training (US4) — launch a real AMLB benchmark on an integrated framework, watch jobs.

Pick an integrated framework + constraint → `runner.launch()` spawns a detached `docker run` of
the framework's AMLB image on the `mvp` benchmark; results are ingested into `runs` (and show up
in Evaluation). The jobs table auto-refreshes while anything is running.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import repo, runner  # noqa: E402

theme.inject()
_PILL = {"done": "ok", "running": "run", "failed": "fail", "queued": "queue", "cancelled": "queue"}

# completion toast for a watched job
_w = st.session_state.get("_job")
if _w:
    jobs = runner.list_jobs()
    row = jobs[jobs["training_run_id"] == _w] if not jobs.empty else jobs
    if not row.empty and row.iloc[0]["status"] in ("done", "failed"):
        s = row.iloc[0]["status"]
        st.toast(f"Job #{_w}: {s}", icon="✅" if s == "done" else "⚠️")
        del st.session_state["_job"]

theme.pagehead("Training", "Launch an AMLB benchmark on an integrated framework")

runnable = runner.list_runnable()
if not runnable:
    st.info("No integrated frameworks yet — integrate one on the **Methods** page first "
            "(its Docker image must be present to run).")
    st.stop()

st.caption(runner.host_summary())

st.subheader("Launch a run")
c1, c2 = st.columns(2)
fw = c1.selectbox("Framework", runnable)
cons = runner.list_constraints() or [runner.DEFAULT_CONSTRAINT]
ci = cons.index(runner.DEFAULT_CONSTRAINT) if runner.DEFAULT_CONSTRAINT in cons else 0
con = c2.selectbox("Constraint", cons, index=ci)

# what the framework's bundled AMLB image can actually do (community images vary by AMLB version)
_caps = runner.framework_caps(fw)
if not _caps["constraint"]:
    st.error(f"**{fw}**'s Docker image bundles an AMLB version with **no constraint support** "
             f"(typical of `:stable` tags), so passing `{con}` fails with *unrecognized arguments*. "
             f"It can't be run one-click here — integrate a newer image tag for {fw} on the "
             "**Methods** page.")

# compatibility of the chosen framework on THIS machine (empirical history + emulation heuristic)
_cp = runner.compat(fw, (repo.get_method(fw) or {}).get("kind"), runner.run_history())
if _cp["msg"]:
    {"ok": st.success, "fail": st.error, "warn": st.warning}[_cp["level"]](
        f'**{fw}** · {_cp["label"]} — {_cp["msg"]}')

# pick which catalog datasets to train on (US8 ↔ US4); non-runnable ones are disabled
_cat = runner.list_trainable_datasets()
_run_ds = [d for d in _cat if d["runnable"]]
_blocked = [d for d in _cat if not d["runnable"]]
# this framework's image may be too old to run uploaded/file datasets (no OpenML task id) — exclude
# them up front so one incompatible upload can't crash the whole job (mirrors runner.launch).
_incompat = [d for d in _run_ds if not _caps["file_datasets"] and not d["task_id"]]
if _incompat:
    _run_ds = [d for d in _run_ds if d["task_id"]]
# chip label = just the dataset name (no truncation); type/source shown in the summary below
_type = {d["name"]: (d.get("type") or "?") for d in _run_ds}
picked = st.multiselect(
    "Datasets to train on", [d["name"] for d in _run_ds],
    default=[d["name"] for d in _run_ds],
    help="From the Datasets catalog. Add more via the Datasets page (Upload CSV / OpenML).",
)
if picked:
    from collections import Counter
    _bd = Counter(_type[n] for n in picked)
    _summary = " · ".join(f"{v} {k}" for k, v in sorted(_bd.items()))
    st.caption(f"**{len(picked)}** dataset(s) selected — {_summary}")
if _blocked:
    st.caption("Not runnable (need an OpenML task id, or an uploaded file + target column): "
               + ", ".join(d["name"] for d in _blocked))
if _incompat:
    st.caption(f"⚠️ Excluded for **{fw}**: " + ", ".join(d["name"] for d in _incompat)
               + " — its AMLB image is too old to run uploaded/file datasets (no OpenML task id). "
                 "Run these on a framework with a current image, or integrate a newer tag.")

_c = runner.constraint_info(con)
if _c:
    budget = f"{_c['seconds']}s" if (_c["seconds"] or 0) < 120 else f"{(_c['seconds'] or 0)//60} min"
    st.caption(f"Each dataset is trained with a **{budget}** time budget · **{_c['folds']}** fold "
               f"· **{_c['cores']}** cores. Results flow to Evaluation.")

_ids = [d["dataset_id"] for d in _run_ds if d["name"] in picked]

# gate: a framework that already FAILED on this machine is blocked unless explicitly overridden
_blocked = _cp["level"] == "fail"
_override = False
if _blocked:
    _override = st.checkbox(f"Run **{fw}** anyway — it failed on this machine before "
                            "(likely to fail/hang again)", value=False)
if st.button(f"🚀 Launch on {len(_ids)} dataset(s)", type="primary",
             disabled=(not _ids) or (_blocked and not _override) or (not _caps["constraint"])):
    with st.spinner(f"Starting {fw}…"):
        tr_id, status = runner.launch(fw, _ids, con)
    _err = {"failed": f"Could not start {fw} — is Docker running?",
            "no_constraint": f"{fw}'s image has no constraint support — can't run it here.",
            "no_datasets": f"No datasets {fw}'s image can run — pick OpenML datasets."}
    if status in _err:
        st.toast(_err[status], icon="⚠️")
    else:
        st.session_state["_job"] = tr_id
        st.toast(f"Launched job #{tr_id} · {fw} on {len(_ids)} dataset(s)", icon="🚀")
    st.rerun()

st.subheader("Jobs")


def _dur(a, b):
    """Compact duration between two timestamps (b−a); a is start, b is end-or-now."""
    if a is None or pd.isna(a) or b is None or pd.isna(b):
        return "—"
    s = int(max(0, (b - a).total_seconds()))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


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

# Stop controls live OUTSIDE the auto-refreshing fragment below: buttons inside a `run_every`
# fragment race the periodic rerun and silently drop clicks. Rendered once per page run; a job
# that finishes on its own triggers a full rerun (fragment tail), which clears these.
if _jobs0 is not None and not _jobs0.empty:
    for _, _j in _jobs0[_jobs0["status"] == "running"].iterrows():
        _jid = int(_j["training_run_id"])
        _sc = st.columns([4, 1])
        _sc[0].caption(f"Job #{_jid} · {_j.get('framework') or '—'} is running — Stop kills its "
                       "Docker container immediately.")
        if _sc[1].button("⏹ Stop", key=f"stop_{_jid}", use_container_width=True):
            _stopped = runner.cancel(_jid)
            st.toast(f"Stopped job #{_jid}" if _stopped else f"Job #{_jid} already finished",
                     icon="⏹️" if _stopped else "ℹ️")
            st.rerun()


@st.fragment(run_every=("3s" if _busy0 else None))
def _jobs():
    df, busy = _safe_jobs()
    if df is None:
        return
    if df.empty:
        st.caption("No runs yet — launch one above.")
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
        end = j["finished_at"] if not pd.isna(j["finished_at"]) else now
        rows.append([
            f'<span class="mono">#{int(j["training_run_id"])}</span>',
            f'<b>{j.get("framework") or "—"}</b>',
            j.get("constraint") or "—",
            theme.pill(st_, _PILL.get(st_, "queue")),
            f'{int(j.get("datasets", 0))}',
            f'{int(j["runs"])}',
            f'<span class="mono">{str(j["started_at"])[:19] if not pd.isna(j["started_at"]) else "—"}</span>',
            f'<span class="mono">{_dur(j["started_at"], end)}</span>',
        ])
    theme.table(["Job", "Framework", "Constraint", "Status", "Datasets", "Runs", "Started", "Duration"], rows)

    failed = df[(df["status"] == "failed") & df["error"].notna()] if "error" in df else df.iloc[0:0]
    for _, j in failed.iterrows():
        with st.expander(f"⚠️ Job #{int(j['training_run_id'])} ({j.get('framework')}) — why it failed"):
            st.code(str(j["error"]), language=None)

    if busy:
        st.caption("⟳ Auto-refreshing every 3s while a job is running.")
    if _busy0 and not busy:
        st.rerun()


_jobs()
