"""Methods — catalog (list) + per-framework detail, one page (no extra sidebar nav entry).

Detail is the SAME Methods page in a `?m=<name>` mode (query param) — it does not register a new
page in the sidebar. Click a card → detail; "← Back" → list. One-click Integrate/Retry + Docker.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import integration, repo, runner  # noqa: E402

theme.inject()
_PILL = {"integrated": "ok", "integrating": "run", "available": "queue",
         "failed": "fail", "setup_pending": "warn"}


def _ver_from_tag(tag):
    """Framework version embedded in the image tag: '0.15.0-v2.1.6' → '0.15.0'."""
    if not tag:
        return None
    return tag.split("-v")[0] if "-v" in tag else tag.split("-")[0]


def _kick(name):
    with st.spinner(f"Starting {name}…"):
        integration.integrate(name)
    st.session_state["_toast"] = (f"Integrating {name}…", ":material/hourglass_top:")  # survive rerun
    st.session_state["_watch"] = name                            # toast again when it finishes


# show a queued toast (start), and a completion toast when a watched pull finishes
_pt = st.session_state.pop("_toast", None)
if _pt:
    st.toast(_pt[0], icon=_pt[1])
_w = st.session_state.get("_watch")
if _w:
    _ws = integration.integration_status(_w)["status"]
    if _ws in ("integrated", "failed"):
        st.toast(f"{_w}: {_ws}",
                 icon=":material/check_circle:" if _ws == "integrated" else ":material/warning:")
        del st.session_state["_watch"]

# make seeded 'integrated' statuses truthful against actual local images (once per session)
if not st.session_state.get("_reconciled"):
    integration.reconcile()
    st.session_state["_reconciled"] = True

# Docker availability gates Integrate up front — no point pulling a multi-GB image when it's down.
_docker_up = integration._docker_available()

df_all = repo.list_methods()
if df_all.empty:
    theme.pagehead("Methods", "Framework catalog &amp; integration")
    st.info("No methods yet — run `python -m storage.seed` to populate the catalog.")
    st.stop()

selected = st.query_params.get("m")

# ===================== DETAIL (same page, ?m=) =====================
if selected and (df_all["name"] == selected).any():
    theme.pagehead(f"Method · {selected}")
    st.markdown('<a href="?" target="_self" style="text-decoration:none;color:var(--teal);font-size:13px;">'
                '← Back to all methods</a>', unsafe_allow_html=True)

    def _render(m):
        status = m.get("integration_status", "?")
        cp = runner.compat(selected, m.get("kind"), runner.run_history())
        chip = f' &nbsp; {theme.pill(cp["label"], cp["level"])}' if cp["label"] else ""
        st.markdown(f'### {selected} &nbsp; {theme.pill(status, _PILL.get(status, "queue"))}{chip}',
                    unsafe_allow_html=True)

        _img = m.get("docker_image")
        _present = integration.image_present(_img)

        # readiness note for the current status — paired with the compat note into ONE box below
        # (rather than two coloured boxes sandwiching the detail table).
        def _readiness():
            if status == "failed" and m.get("last_error"):
                return ("fail", f"Last error: {m['last_error']}")
            if status == "integrating":
                return ("info", "Pulling image… this view auto-refreshes.")
            if status == "setup_pending":
                return ("warn", "Needs manual setup (e.g. Java for H2O) — not one-click.")
            if status == "integrated" and not _present:
                return ("warn", "Marked integrated, but the image isn't pulled locally — "
                                "click Integrate to pull it.")
            if status == "integrated" and _present:
                caps = runner.framework_caps(selected)
                if not caps["constraint"]:
                    return ("fail", "Image is present, but its bundled **AMLB has no constraint "
                                    "support** (typical of `:stable` tags) — it **can't be launched "
                                    "one-click** on the Training page. Integrate a newer image tag.")
                if not caps["file_datasets"]:
                    return ("warn", "Image present, but its bundled AMLB is **too old to run "
                                    "uploaded/file datasets** (no OpenML task id) — only OpenML "
                                    "datasets run; uploads are auto-excluded at launch.")
                return ("ok", "Image present — runnable on the Training page.")
            return None

        # ONE consolidated notice: compatibility + readiness, coloured by the most severe of the two.
        _rd = _readiness()
        _notes = ([(cp["level"], cp["msg"])] if cp["msg"] else []) + ([_rd] if _rd else [])
        if _notes:
            _sev = {"fail": 3, "warn": 2, "info": 1, "ok": 0}
            _lvl = max(_notes, key=lambda x: _sev.get(x[0], 0))[0]
            {"ok": st.success, "fail": st.error, "warn": st.warning, "info": st.info}[_lvl](
                "\n\n".join(t for _, t in _notes))

        _sz = integration.image_size_bytes(_img)
        fields = [("Kind", m.get("kind")),
                  ("Version", m.get("version") or _ver_from_tag(m.get("image_tag"))),
                  ("Preset", m.get("preset")),
                  ("Resource class", f'{cp["weight"]} ({"amd64 / emulated" if cp["backend"] not in ("native",) else "native"})'),
                  ("Image", _img), ("Tag", m.get("image_tag")),
                  ("Image size", f"{_sz / 1e9:.2f} GB" if _sz else None),
                  ("Last integration", m.get("last_integration_at")), ("Project", m.get("project_url"))]
        theme.table(["Field", "Value"],
                    [[f, f'<span class="mono">{v}</span>'] for f, v in fields if v not in (None, "")])

        # if a training job is currently running this framework, let the user stop it here
        # (its container holds the image — must stop before the image can be removed)
        _jobs = runner.list_jobs()
        if not _jobs.empty:
            _busy_jobs = _jobs[(_jobs["status"] == "running") & (_jobs["framework"] == selected)]
            for _, _j in _busy_jobs.iterrows():
                _jid = int(_j["training_run_id"])
                st.warning(f"Job #{_jid} is running this framework — stop it to free the image.")
                if st.button(f"Stop job #{_jid}", key=f"stopm_{_jid}", icon=":material/stop:"):
                    runner.cancel(_jid)
                    st.toast(f"Stopped job #{_jid}", icon=":material/stop_circle:")
                    st.rerun()

        # action buttons (the status/compat messages are already shown in the notice box above)
        if status in ("available", "failed"):
            if st.button("Retry integration" if status == "failed" else "Integrate",
                         type="primary", key=f"int_{selected}", disabled=not _docker_up,
                         icon=":material/refresh:" if status == "failed" else ":material/download:"):
                _kick(selected)
                st.rerun()
            if not _docker_up:
                st.caption("Docker engine isn't running — start Docker/Rancher to integrate.")
        elif status == "integrated" and _present:
            _free = f" (free {_sz / 1e9:.1f} GB)" if _sz else ""
            if st.button(f"Remove image{_free}", key=f"rmi_{selected}", icon=":material/delete:"):
                ok = integration.remove_image(_img)
                integration.reconcile()           # image gone → status back to 'available'
                st.toast(f"Removed {selected} image" if ok else f"Could not remove {selected}",
                         icon=":material/delete:" if ok else ":material/warning:")
                st.rerun()

    m0 = df_all.query("name == @selected").iloc[0]      # reuse loaded row — no extra query
    if m0["integration_status"] == "integrating":
        @st.fragment(run_every="2s")
        def _live():
            m = repo.get_method(selected)
            _render(m)
            if m and m["integration_status"] != "integrating":
                st.rerun()
        _live()
    else:
        slot = st.empty()
        slot.markdown('<div class="skel" style="width:35%"></div>'
                      '<div class="skel"></div><div class="skel" style="width:80%"></div>',
                      unsafe_allow_html=True)
        with slot.container():
            _render(m0)
    st.stop()

# ===================== LIST =====================
theme.pagehead("Methods", "Framework catalog &amp; integration")

integratable = df_all.query("integration_status in ('available','failed')")["name"].tolist()
st.subheader("Integrate a framework")

# One toolbar row: pick a framework · Integrate (primary) · Re-check (secondary). Re-check re-syncs
# the labels with reality (status is a label; the truth is whether `docker image inspect` finds the
# image — a Docker restart/crash can leave an 'integrated' label stale).
tb = st.columns([6, 1.6, 1.6], vertical_alignment="bottom")
pick = tb[0].selectbox("Available or failed (pull its AMLB Docker image)",
                       integratable or ["— none —"], label_visibility="collapsed",
                       disabled=not integratable)
if tb[1].button("Integrate", type="primary", use_container_width=True,
                disabled=not (integratable and _docker_up)):
    _kick(pick)
    st.rerun()
if tb[2].button("Re-check", icon=":material/refresh:", use_container_width=True,
                help="Re-sync each framework's status against the images actually pulled locally."):
    changed = integration.reconcile()
    st.toast(f"Re-checked — {len(changed)} status updated" if changed else "Re-checked — all in sync",
             icon=":material/check_circle:")
    st.rerun()
st.caption("Status = whether the image is actually pulled locally."
           + ("" if _docker_up else " Docker engine isn't running — start Docker/Rancher to integrate."))

with st.expander("Docker storage — disk usage & cleanup", icon=":material/storage:"):
    disk = integration.docker_disk()
    if disk:
        theme.table(["Type", "Size", "Reclaimable"],
                    [[d["type"], f'<span class="mono">{d["size"]}</span>',
                      f'<span class="mono">{d["reclaimable"]}</span>'] for d in disk])
    dc1, dc2 = st.columns([5, 2])
    dc1.caption("Reclaim = prune build cache + stopped containers + dangling layers. "
                "Framework images are kept — free those individually on a method's detail page.")
    if dc2.button("Reclaim space", use_container_width=True, icon=":material/cleaning_services:"):
        with st.spinner("Pruning…"):
            summary = integration.reclaim_space()
        st.toast(f"Reclaimed — {summary}", icon=":material/check_circle:")
        st.rerun()

# Browse the catalog — search by name + filter by status. Widgets live OUTSIDE the auto-refresh
# fragment (so a periodic rerun can't reset them); the fragment reads their values from session.
st.subheader("Catalog")
_fc = st.columns([2, 3])
_fc[0].text_input("Search frameworks", placeholder="Filter by name…",
                  label_visibility="collapsed", key="m_q")
_fc[1].segmented_control("Filter by status",
                         ["integrated", "available", "failed", "setup_pending"],
                         selection_mode="multi", label_visibility="collapsed", key="m_status")

_busy = bool((df_all["integration_status"] == "integrating").any())


@st.fragment(run_every=("2s" if _busy else None))
def _catalog():
    df = repo.list_methods()
    total = len(df)
    _q = (st.session_state.get("m_q") or "").strip().lower()
    _sf = st.session_state.get("m_status") or []
    if _q:
        df = df[df["name"].str.lower().str.contains(_q, na=False)]
    if _sf:
        df = df[df["integration_status"].isin(_sf)]
    st.caption(f"Showing **{len(df)}** of {total} frameworks"
               + (" — none match the filter." if df.empty else ""))

    hist = runner.run_history()
    cards = ""
    for _, m in df.iterrows():
        skind = _PILL.get(m.get("integration_status"), "queue")
        cp = runner.compat(m["name"], m.get("kind"), hist)
        chip = f'&nbsp;{theme.pill(cp["label"], cp["level"])}' if cp["label"] else ""
        card = (f'<div class="card"><h3 style="margin-top:0">{m["name"]}</h3>'
                f'{theme.pill(m.get("integration_status","?"), skind)}{chip}</div>')
        cards += (f'<a href="?m={m["name"]}" target="_self" '
                  f'style="text-decoration:none;color:inherit;display:block">{card}</a>')
    st.markdown(f'<div class="cards">{cards}</div>', unsafe_allow_html=True)
    if _busy and not (df["integration_status"] == "integrating").any():
        st.rerun()


_catalog()
