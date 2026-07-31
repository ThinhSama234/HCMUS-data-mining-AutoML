"""Training (US4) — launch a real AMLB benchmark on an integrated framework.

Pick an integrated framework + constraint + datasets → `runner.launch()` spawns a detached
`docker run` of the framework's AMLB image; results are ingested into `runs` (and show up in
Evaluation). Monitor progress on the **Jobs** page (this page jumps there after a launch).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import repo, runner  # noqa: E402

theme.inject()
theme.pagehead("Training", "Launch an AMLB benchmark on an integrated framework")

runnable = runner.list_runnable()
if not runnable:
    st.info("No integrated frameworks yet — integrate one on the **Methods** page first "
            "(its Docker image must be present to run).")
    st.stop()

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

# compatibility of the chosen framework on THIS machine → a compact, self-explanatory callout:
# plain-language status + the reason + what to do, all visible (no hover). A newcomer shouldn't have
# to decode "Failed here" or hover to learn why.
_cp = runner.compat(fw, (repo.get_method(fw) or {}).get("kind"), runner.run_history())
if _cp["level"] == "fail":
    st.markdown(theme.status_note(
        "fail", f"{fw} probably won't run on this machine.", _cp.get("msg"),
        "Enable “Run anyway” below to try regardless, or pick a lighter-weight framework."),
        unsafe_allow_html=True)
elif _cp["level"] == "warn":
    st.markdown(theme.status_note(
        "warn", f"{fw} may run slowly or unreliably here.", _cp.get("msg")),
        unsafe_allow_html=True)
elif _cp["level"] == "ok" and _cp.get("msg"):
    st.markdown(theme.status_note("ok", f"{fw} is compatible with this machine.", _cp.get("msg")),
                unsafe_allow_html=True)

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
    st.caption(f"Excluded for **{fw}**: " + ", ".join(d["name"] for d in _incompat)
               + " — its AMLB image is too old to run uploaded/file datasets (no OpenML task id). "
                 "Run these on a framework with a current image, or integrate a newer tag.")

_c = runner.constraint_info(con)
if _c:
    budget = f"{_c['seconds']}s" if (_c["seconds"] or 0) < 120 else f"{(_c['seconds'] or 0)//60} min"
    _folds = _c["folds"] or 1
    _cv = (f"**{_folds}-fold** cross-validation" if _folds > 1 else "a **single split**")
    _agg = "**mean ± std** over the folds" if _folds > 1 else "the single-split score"
    st.caption(f"Each dataset is evaluated with {_cv} · **{budget}** time budget · **{_c['cores']}** "
               f"cores, applied equally to every framework. AMLB uses a **fixed per-fold seed** "
               f"(classification splits on OpenML tasks are stratified); Evaluation reports {_agg}.")

_ids = [d["dataset_id"] for d in _run_ds if d["name"] in picked]

# gate: a framework that already FAILED on this machine is blocked unless explicitly overridden
_failed_here = _cp["level"] == "fail"
_override = False
if _failed_here:
    _override = st.checkbox(f"Run **{fw}** anyway — it failed on this machine before "
                            "(likely to fail/hang again)", value=False)
if st.button(f"Launch on {len(_ids)} dataset(s)", type="primary", icon=":material/play_arrow:",
             disabled=(not _ids) or (_failed_here and not _override) or (not _caps["constraint"])):
    with st.spinner(f"Starting {fw}…"):
        tr_id, status = runner.launch(fw, _ids, con)
    _err = {"failed": f"Could not start {fw} — is Docker running?",
            "no_constraint": f"{fw}'s image has no constraint support — can't run it here.",
            "no_datasets": f"No datasets {fw}'s image can run — pick OpenML datasets."}
    if status in _err:
        st.toast(_err[status], icon=":material/warning:")
        st.rerun()
    else:
        st.session_state["_job"] = tr_id           # Jobs page watches this for a completion toast
        st.switch_page("views/jobs.py")            # jump to monitoring
