"""Datasets — US8: real ingestion. Upload CSV / Add-from-OpenML → object store + DB; list from DB."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import adapt, ingest, objectstore, repo  # noqa: E402

theme.inject()
theme.pagehead("Datasets", "Upload a CSV or add from OpenML — stored in object store &amp; DB")

def _render_kaggle_verdicts(verdicts):
    """Show the adaptability-rule outcome: a tick per pass, an error + hint on the first reject."""
    for v in verdicts:
        if v.ok:
            st.caption(f"✓ {v.rule_id}")
        else:
            st.error(f"{v.rule_id} — {v.reason}")
            if v.hint:
                st.caption(v.hint)


# --- ingest: pick ONE source, then show only that input (cleaner than three stacked forms) ---
_SOURCES = ["Upload CSV", "OpenML", "Kaggle"]
src = st.segmented_control("Add a dataset from", _SOURCES, default="Upload CSV",
                           selection_mode="single", key="ds_source") or "Upload CSV"

if src == "Upload CSV":
    up = st.file_uploader("CSV file", type=["csv"])
    if up is not None and st.button("Ingest upload", type="primary", icon=":material/upload:"):
        try:
            with st.spinner(f"Ingesting {up.name}…"):     # spinner while processing
                did = ingest.ingest_upload(up.getvalue(), up.name)
            st.toast(f"Ingested {up.name} → id {did}", icon=":material/check_circle:")
        except Exception as exc:
            st.toast(f"Rejected: {exc}", icon=":material/warning:")

elif src == "OpenML":
    oc1, oc2 = st.columns(2)
    tid = oc1.text_input("OpenML task id", placeholder="e.g. 168757")
    alias = oc2.text_input("Display name (alias)", placeholder="e.g. breast_cancer",
                           help="Friendly name shown in the catalog instead of OpenML's cryptic "
                                "one (e.g. breast_cancer instead of wdbc). Optional.")
    if tid and st.button("Add from OpenML", type="primary", icon=":material/download:"):
        try:
            with st.spinner(f"Fetching OpenML task {tid}…"):
                did = ingest.ingest_openml(int(tid), alias=alias)
            st.toast(f"Added OpenML {tid} → id {did}", icon=":material/check_circle:")
        except Exception as exc:
            st.toast(f"Failed: {exc}", icon=":material/warning:")

elif src == "Kaggle":
    kurl = st.text_input("Kaggle dataset URL", key="kg_url",
                         placeholder="https://www.kaggle.com/datasets/owner/slug")
    if st.button("Fetch", key="kg_fetch", icon=":material/search:"):
        with st.spinner("Listing dataset files…"):
            st.session_state["kg_listing"] = ingest.kaggle_list(kurl)
        st.session_state.pop("kg_staged", None)

    _listing = st.session_state.get("kg_listing")
    if _listing is not None:
        _render_kaggle_verdicts(_listing.verdicts)
        if _listing.ok:
            _tabs = [f.name for f in _listing.files
                     if str(f.name).lower().endswith(adapt.TABULAR_EXTS)]
            _chosen = _tabs[0] if len(_tabs) == 1 else st.selectbox("Tabular file", _tabs, key="kg_file")
            _staged = st.session_state.get("kg_staged")
            if _staged is None or _staged.file_name != _chosen:
                with st.spinner(f"Reading {_chosen}…"):
                    _staged = ingest.kaggle_read(_listing.ref, _chosen)
                st.session_state["kg_staged"] = _staged
            _render_kaggle_verdicts(_staged.verdicts)
            if _staged.ok:
                _target = st.selectbox("Target column", _staged.columns,
                                       index=len(_staged.columns) - 1, key="kg_target")
                if st.button("Import from Kaggle", type="primary", key="kg_import"):
                    _res = ingest.kaggle_import(_staged, _target)
                    _render_kaggle_verdicts(_res.verdicts)
                    if _res.ok:
                        _verb = "Already in catalog" if _res.deduped else "Imported"
                        st.toast(f"{_verb} → id {_res.dataset_id}", icon=":material/check_circle:")
                        st.session_state.pop("kg_listing", None)
                        st.session_state.pop("kg_staged", None)

# --- catalog (from DB) ---
df = repo.list_datasets()
if df.empty:
    st.info("No datasets yet — upload a CSV or add an OpenML task above.")
else:
    df = df.copy()

    # Archived datasets are hidden by default (from this catalog view AND the Training picker);
    # toggle to see/unarchive them. Keeps the catalog focused on the sets you're actually testing.
    _show_arch = st.toggle("Show archived", value=False, key="ds_show_arch",
                           help="Archived datasets stay in the catalog but are hidden from Training.")
    if "archived" in df.columns and not _show_arch:
        df = df[~df["archived"].fillna(False)].reset_index(drop=True)

    # Catalog overview (report figures Hình 1-2): task-type composition + size/#features per dataset.
    if not df.empty and "task_type" in df.columns and df["task_type"].notna().any():
        st.subheader("Catalog overview", help=(
            "Composition of the benchmark suite by task type, and each dataset's scale "
            "(rows, log scale) and feature count — sourced from the catalog."))
        oc1, oc2 = st.columns(2)
        with oc1:
            comp = df["task_type"].fillna("unknown").value_counts().reset_index()
            comp.columns = ["task_type", "n"]
            # composition donut → monochrome teal ramp (amber stays a signal-only accent, not a big
            # fill), so the three overview panels read as one teal-led system.
            _TEAL_RAMP = ["#0C6E6A", "#4E9B98", "#8FBAB8", "#C2D6D4"]
            pfig = px.pie(comp, names="task_type", values="n", hole=0.45,
                          color_discrete_sequence=_TEAL_RAMP)
            pfig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="")
            st.plotly_chart(pfig)
        with oc2:
            if "n_instances" in df.columns and df["n_instances"].notna().any():
                sz = df[df["n_instances"].notna()].sort_values("n_instances")
                bfig = px.bar(sz, x="n_instances", y="name", orientation="h", log_x=True,
                              color_discrete_sequence=[theme.TEAL],
                              labels={"n_instances": "Rows (log)", "name": ""})
                bfig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(bfig)
        if "n_features" in df.columns and df["n_features"].notna().any():
            ft = df[df["n_features"].notna()].sort_values("n_features")
            ffig = px.bar(ft, x="n_features", y="name", orientation="h",
                          color_discrete_sequence=[theme.TEAL],   # teal-led overview; amber is signal-only
                          labels={"n_features": "Features", "name": ""})
            ffig.update_layout(height=max(180, 26 * len(ft) + 40), margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(ffig)

    # presigned download URL (per-row Download action) instead of the opaque s3:// uri
    df["download"] = [objectstore.presign(u) if isinstance(u, str) and u else None
                      for u in df.get("storage_uri", [None] * len(df))]
    total = len(df)

    # Rows/page is a display setting → stays top-left; page navigation (‹ ›) goes in a bottom bar.
    _paginate = total > 10
    start, end, page, n_pages = 0, total, 1, 1
    if _paginate:
        page_size = st.columns([1.3, 5])[0].selectbox("Rows/page", [10, 25, 50, 100], index=0)
        n_pages = (total + page_size - 1) // page_size
        page = max(1, min(st.session_state.get("ds_page", 1), n_pages))
        st.session_state["ds_page"] = page
        start, end = (page - 1) * page_size, (page - 1) * page_size + page_size

    # Rendered row-by-row (not st.dataframe) so the last "Action" column can hold real per-row
    # buttons — archive, delete, download — which a canvas-based dataframe can't do.
    _W = [0.7, 3, 1.2, 1.4, 1.2, 1.1, 2.0]
    _head = st.columns(_W)
    for _c, _lbl in zip(_head, ["ID", "Name", "Source", "Task", "Rows", "Size", "Action"]):
        _c.markdown(f'<span class="section-lbl">{_lbl}</span>', unsafe_allow_html=True)

    for _, r in df.iloc[start:end].iterrows():
        did = int(r["dataset_id"])
        c = st.columns(_W, vertical_alignment="center")
        c[0].write(did)
        c[1].write(r["name"])
        c[2].write(r.get("source") or "—")
        c[3].write(r.get("task_type") or "—")
        _ni = r.get("n_instances")
        c[4].write(f"{int(_ni):,}" if pd.notna(_ni) else "—")
        c[5].write(r.get("size_tier") or "—")
        with c[6]:
            b = st.columns(3)
            _arch = bool(r.get("archived"))
            if b[0].button("", key=f"arch_{did}",
                           icon=":material/unarchive:" if _arch else ":material/archive:",
                           help="Unarchive" if _arch else "Archive — hide from Training"):
                repo.set_archived([did], not _arch)
                st.toast(("Unarchived " if _arch else "Archived ") + str(r["name"]),
                         icon=":material/check_circle:")
                st.rerun()
            if b[1].button("", key=f"del_{did}", icon=":material/delete:",
                           help="Delete permanently (also removes linked runs)"):
                repo.delete_datasets([did])
                st.toast(f"Deleted {r['name']}", icon=":material/delete:")
                st.rerun()
            if r.get("download"):
                b[2].link_button("", url=r["download"], icon=":material/download:", help="Download")

    # bottom bar: "Showing …" at the left, ‹ Page x / n › pushed to the right
    if _paginate:
        bl, _spacer, bp, bn, bx = st.columns([4, 3, 0.7, 1.5, 0.7], vertical_alignment="center")
        bl.caption(f"Showing {start + 1}–{min(end, total)} of {total} datasets")
        if bp.button("‹", key="ds_prev", disabled=page <= 1, width="stretch"):
            st.session_state["ds_page"] = page - 1
            st.rerun()
        bn.markdown(f'<div style="text-align:center;font-size:13px">Page <b>{page}</b> / {n_pages}'
                    '</div>', unsafe_allow_html=True)
        if bx.button("›", key="ds_next", disabled=page >= n_pages, width="stretch"):
            st.session_state["ds_page"] = page + 1
            st.rerun()
    else:
        st.caption(f"Showing 1–{total} of {total} datasets")
