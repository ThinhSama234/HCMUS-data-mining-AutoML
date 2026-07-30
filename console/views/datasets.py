"""Datasets — US8: real ingestion. Upload CSV / Add-from-OpenML → object store + DB; list from DB."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
                st.caption(f"💡 {v.hint}")


# --- ingest actions ---
c1, c2 = st.columns(2)
with c1:
    up = st.file_uploader("Upload CSV", type=["csv"])
    if up is not None and st.button("Ingest upload", type="primary"):
        try:
            with st.spinner(f"Ingesting {up.name}…"):     # spinner while processing
                did = ingest.ingest_upload(up.getvalue(), up.name)
            st.toast(f"Ingested {up.name} → id {did}", icon="✅")   # transient toast, not inline text
        except Exception as exc:
            st.toast(f"Rejected: {exc}", icon="⚠️")
with c2:
    tid = st.text_input("OpenML task id", placeholder="e.g. 168757")
    if tid and st.button("Add from OpenML", type="primary"):
        try:
            with st.spinner(f"Fetching OpenML task {tid}…"):
                did = ingest.ingest_openml(int(tid))
            st.toast(f"Added OpenML {tid} → id {did}", icon="✅")
        except Exception as exc:
            st.toast(f"Failed: {exc}", icon="⚠️")

# --- add from Kaggle (public link, spec 006) ---
st.divider()
st.markdown("**Add from Kaggle (public link)**")
kurl = st.text_input("Kaggle dataset URL", placeholder="https://www.kaggle.com/datasets/owner/slug",
                     key="kg_url")
if st.button("Fetch", key="kg_fetch"):
    with st.spinner("Listing dataset files…"):
        st.session_state["kg_listing"] = ingest.kaggle_list(kurl)
    st.session_state.pop("kg_staged", None)

_listing = st.session_state.get("kg_listing")
if _listing is not None:
    _render_kaggle_verdicts(_listing.verdicts)
    if _listing.ok:
        _tabs = [f.name for f in _listing.files if str(f.name).lower().endswith(adapt.TABULAR_EXTS)]
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
                    st.toast(f"{_verb} → id {_res.dataset_id}", icon="✅")
                    st.session_state.pop("kg_listing", None)
                    st.session_state.pop("kg_staged", None)

# --- catalog (from DB) ---
df = repo.list_datasets()
if df.empty:
    st.info("No datasets yet — upload a CSV or add an OpenML task above.")
else:
    df = df.copy()

    # Catalog overview (report figures Hình 1-2): task-type composition + size/#features per dataset.
    if "task_type" in df.columns and df["task_type"].notna().any():
        st.subheader("Catalog overview", help=(
            "Composition of the benchmark suite by task type, and each dataset's scale "
            "(rows, log scale) and feature count — sourced from the catalog."))
        oc1, oc2 = st.columns(2)
        with oc1:
            comp = df["task_type"].fillna("unknown").value_counts().reset_index()
            comp.columns = ["task_type", "n"]
            pfig = px.pie(comp, names="task_type", values="n", hole=0.45)
            pfig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="")
            st.plotly_chart(pfig, use_container_width=True)
        with oc2:
            if "n_instances" in df.columns and df["n_instances"].notna().any():
                sz = df[df["n_instances"].notna()].sort_values("n_instances")
                bfig = px.bar(sz, x="n_instances", y="name", orientation="h", log_x=True,
                              color_discrete_sequence=[theme.TEAL],
                              labels={"n_instances": "Rows (log)", "name": ""})
                bfig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(bfig, use_container_width=True)
        if "n_features" in df.columns and df["n_features"].notna().any():
            ft = df[df["n_features"].notna()].sort_values("n_features")
            ffig = px.bar(ft, x="n_features", y="name", orientation="h",
                          color_discrete_sequence=[theme.AMBER],
                          labels={"n_features": "Features", "name": ""})
            ffig.update_layout(height=max(180, 26 * len(ft) + 40), margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(ffig, use_container_width=True)

    # presigned download link instead of the opaque s3:// uri (LinkColumn renders it as a button)
    df["download"] = [objectstore.presign(u) if isinstance(u, str) and u else None
                      for u in df.get("storage_uri", [None] * len(df))]
    cols = [c for c in ["dataset_id", "name", "source", "status", "openml_task_id", "task_type",
                        "n_instances", "n_features", "n_classes", "minority_fraction",
                        "size_tier", "download"] if c in df.columns]
    view = df[cols]
    total = len(view)

    start, end = 0, total
    if total > 10:                                   # paginate only when it helps
        cc = st.columns([1, 1, 4])
        page_size = cc[0].selectbox("Rows/page", [10, 25, 50, 100], index=0)
        n_pages = (total + page_size - 1) // page_size
        page = cc[1].number_input("Page", min_value=1, max_value=n_pages, value=1, step=1)
        start, end = (page - 1) * page_size, (page - 1) * page_size + page_size

    st.dataframe(
        view.iloc[start:end], width="stretch", hide_index=True,
        column_config={"download": st.column_config.LinkColumn("File", display_text="⬇")},
    )
    st.caption(f"Showing {start + 1}–{min(end, total)} of {total} datasets")
