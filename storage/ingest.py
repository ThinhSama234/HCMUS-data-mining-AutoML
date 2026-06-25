"""Dataset ingestion (FR-015, FR-016) — file → object store, metadata → datasets table.

Both flows return the new dataset_id; the dataset is then selectable for training (SC-008).
"""
from __future__ import annotations

import hashlib
import io
import uuid

import pandas as pd
from sqlalchemy import insert, select

from storage import db, objectstore
from storage.models import datasets


def _size_tier(n):
    if n is None:
        return "unknown"
    return "small" if n < 2_000 else "medium" if n < 50_000 else "large"


def infer_metadata(df: pd.DataFrame, target_column: str | None = None) -> dict:
    """Infer task_type / counts / class balance from a tabular frame (last column = target by default)."""
    if df.shape[1] < 2:
        raise ValueError("dataset needs at least one feature column plus a target")
    target = target_column or df.columns[-1]
    y = df[target]
    n, p = len(df), df.shape[1] - 1
    n_classes, minority, task_type = None, None, None
    if pd.api.types.is_numeric_dtype(y) and y.nunique() > 20:
        task_type = "regression"
    else:
        n_classes = int(y.nunique())
        task_type = "binary" if n_classes == 2 else "multiclass"
        if n_classes == 2:
            vc = y.value_counts(normalize=True)
            minority = float(vc.min())
    return dict(task_type=task_type, target_column=str(target), n_instances=int(n),
                n_features=int(p), n_classes=n_classes, minority_fraction=minority,
                size_tier=_size_tier(n))


def _insert_dataset(eng, **fields) -> int:
    with eng.begin() as conn:
        return conn.execute(insert(datasets).values(**fields)).inserted_primary_key[0]


def ingest_upload(data: bytes, name: str) -> int:
    """Store an uploaded CSV in object storage + a datasets row (source='upload'). FR-015."""
    try:
        df = pd.read_csv(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"not a readable CSV: {exc}") from exc
    meta = infer_metadata(df)  # raises (no row written) if malformed
    uri = objectstore.put("datasets", f"{uuid.uuid4().hex}.csv", data)
    eng = db.init_db()
    return _insert_dataset(eng, name=name, source="upload", file_format="csv",
                           storage_uri=uri, checksum_sha256=hashlib.sha256(data).hexdigest(),
                           status="ready", **meta)


def ingest_openml(task_id: int) -> int:
    """Fetch an OpenML task's dataset → object store (parquet) + a datasets row. FR-016."""
    import openml
    task = openml.tasks.get_task(int(task_id))
    ds = task.get_dataset()
    X, y, _, _ = ds.get_data(target=task.target_name)
    frame = X.copy()
    frame[task.target_name] = y
    meta = infer_metadata(frame, target_column=task.target_name)
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    uri = objectstore.put("datasets", f"openml-{task_id}.parquet", buf.getvalue())
    eng = db.init_db()
    # de-dupe: if this openml task already ingested, return it
    with eng.connect() as c:
        existing = c.execute(select(datasets.c.dataset_id)
                             .where(datasets.c.openml_task_id == int(task_id))).first()
    if existing:
        return existing[0]
    return _insert_dataset(eng, name=ds.name, source="openml", openml_task_id=int(task_id),
                           file_format="parquet", storage_uri=uri, status="ready", **meta)
