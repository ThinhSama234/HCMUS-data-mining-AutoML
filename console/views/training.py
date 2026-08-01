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
con = c2.selectbox(
    "Constraint", cons, index=ci,
    help="A preset resource plan (AMLB-style), the **same for every framework** so the comparison is "
         "fair. The time is the budget **per dataset fold** (not total):\n\n"
         "- **smoke** — 60s / fold, single split · a quick pipeline test, not real results\n"
         "- **1h** — 1 hour / fold × 10-fold CV\n"
         "- **4h** — 4 hours / fold × 10-fold CV\n\n"
         "So a `1h` run on one dataset = up to 10 h of AutoML search (10 folds); heavy → run on CI/Linux.")

# Resource plan for the chosen constraint — surfaced up front so `smoke`/`1h`/`4h` isn't an opaque
# label. The SAME plan (folds + budget + cores + memory) is applied to every framework, which is
# what makes the benchmark a fair comparison.
_rp = runner.constraint_info(con)
if _rp:
    _secs = _rp["seconds"] or 0
    _bud = (f"{_secs}s" if _secs < 120 else f"{_secs // 60} min" if _secs < 3600 else f"{_secs // 3600} h")
    _folds = _rp["folds"] or 1
    # AMLB enforces folds/budget/cores per its constraint; memory is shown only when configured.
    _fields = [
        ("CV folds", str(_folds), "Cross-validation folds per dataset (1 = single split). "
         ">1 → Evaluation reports mean ± std over folds, with lower variance."),
        ("Time budget", f"{_bud} / fold", "Max time the AutoML search gets on each dataset fold "
         "(not total) — the same for every framework. Total ≈ budget × folds × datasets."),
        ("Cores", str(_rp["cores"] or "—"), "CPU cores AMLB gives the framework."),
    ]
    if _rp.get("max_mem_mb"):
        _fields.append(("Memory", f"{_rp['max_mem_mb']} MB", "Memory cap per run."))
    for col, (label, val, hlp) in zip(st.columns(len(_fields)), _fields):
        col.metric(label, val, help=hlp)
    st.caption("This resource plan is applied **equally to every framework** (same folds · budget · "
               "cores"
               + (" · memory" if _rp.get("max_mem_mb") else "")
               + ") so the comparison is fair. AMLB uses a **fixed per-fold seed** (classification "
               "splits on OpenML tasks are stratified); Evaluation reports "
               f"{'**mean ± std** over folds' if _folds > 1 else 'the single-split score'}.")

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


_ids = [d["dataset_id"] for d in _run_ds if d["name"] in picked]

# jobs run via Docker on the host — if this console can't reach the Docker daemon (e.g. it's the
# containerised build, which has no docker socket), a launch would fail instantly with "Docker
# engine not running". Block it and point to the host app instead of letting it fail.
_docker_ok = runner._docker_available()
if not _docker_ok:
    st.warning("This console can't reach Docker, so it can't launch benchmark jobs (they run via "
               "Docker on the host). Open the **host app** at http://localhost:8502 to run.")

# gate: a framework that already FAILED on this machine is blocked unless explicitly overridden
_failed_here = _cp["level"] == "fail"
_override = False
if _failed_here:
    _override = st.checkbox(f"Run **{fw}** anyway — it failed on this machine before "
                            "(likely to fail/hang again)", value=False)
if st.button(f"Launch on {len(_ids)} dataset(s)", type="primary", icon=":material/play_arrow:",
             disabled=(not _docker_ok) or (not _ids) or (_failed_here and not _override)
                      or (not _caps["constraint"])):
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
