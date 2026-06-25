"""Datasets — US8: real ingestion. Upload CSV / Add-from-OpenML → object store + DB; list from DB."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

from console import theme  # noqa: E402
from storage import ingest, objectstore, repo  # noqa: E402

theme.inject()
theme.pagehead("Datasets", "Upload a CSV or add from OpenML — stored in object store &amp; DB")

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

# --- catalog (from DB) ---
df = repo.list_datasets()
if df.empty:
    st.info("No datasets yet — upload a CSV or add an OpenML task above.")
else:
    df = df.copy()
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
