"""Dataset ingestion (FR-015, FR-016) — file → object store, metadata → datasets table.

Both flows return the new dataset_id; the dataset is then selectable for training (SC-008).
"""
from __future__ import annotations

import hashlib
import io
import os
import uuid
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import insert, select

from storage import adapt, db, kaggle_client, objectstore
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


# --- Kaggle import (spec 006) ----------------------------------------------
# Only the acquisition differs (a public Kaggle link); once the rule pipeline (storage/adapt.py)
# passes, everything reuses the upload/openml path: object store + a datasets row built from
# infer_metadata + _insert_dataset. See specs/006-kaggle-dataset-import/contracts/ingest-and-ui.md.

@dataclass
class KaggleListing:
    ref: object
    files: list
    verdicts: list
    ok: bool


@dataclass
class Staged:
    ok: bool
    ref: object
    file_name: str
    df: object
    data: bytes
    checksum: str
    columns: list
    verdicts: list


@dataclass
class ImportResult:
    ok: bool
    dataset_id: int | None
    deduped: bool
    verdicts: list
    error: str | None = None


def _kaggle_max_mb() -> int:
    try:
        return int(os.environ.get("KAGGLE_MAX_FILE_MB", "200"))
    except ValueError:
        return 200


def _read_table(file_name: str, data: bytes) -> pd.DataFrame:
    low = file_name.lower()
    if low.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(data))
    sep = "\t" if low.endswith(".tsv") else ","
    return pd.read_csv(io.BytesIO(data), sep=sep)


def kaggle_list(url: str) -> KaggleListing:
    """Pre-download screening (R1-R5): parse the URL, check creds, list files. Downloads nothing."""
    ctx = adapt.Context(url=url, max_file_mb=_kaggle_max_mb())
    ctx.ref = kaggle_client.parse_url(url)
    ctx.creds = kaggle_client.credentials_present()
    if ctx.ref is not None and ctx.creds:                  # only reach out once URL + creds are sane
        try:
            ctx.files = kaggle_client.get_client().list_files(ctx.ref)
        except Exception as exc:                           # KaggleAccessError, ImportError, …
            ctx.list_error = str(exc)
    verdicts = adapt.evaluate(ctx, {"url", "list"})
    return KaggleListing(ref=ctx.ref, files=ctx.files or [], verdicts=verdicts,
                         ok=adapt.all_ok(verdicts))


def kaggle_read(ref, file_name: str) -> Staged:
    """Download the chosen file, parse it, run R6 (shape). Caches the frame + bytes for import."""
    ctx = adapt.Context(ref=ref, file_name=file_name, max_file_mb=_kaggle_max_mb())
    data, checksum, columns = b"", "", []
    try:
        data = kaggle_client.get_client().download_file(ref, file_name,
                                                        ctx.max_file_mb * 1024 * 1024)
        ctx.df = _read_table(file_name, data)
        columns = list(ctx.df.columns)
        checksum = hashlib.sha256(data).hexdigest()
    except Exception as exc:
        ctx.parse_error = str(exc)
    verdicts = adapt.evaluate(ctx, {"shape"})
    return Staged(ok=adapt.all_ok(verdicts), ref=ref, file_name=file_name, df=ctx.df,
                  data=data, checksum=checksum, columns=columns, verdicts=verdicts)


def kaggle_import(staged: "Staged", target_column: str) -> ImportResult:
    """Run R7 (target), dedupe by checksum, then store + insert a datasets row (source='kaggle')."""
    ctx = adapt.Context(df=staged.df, target_column=target_column)
    verdicts = adapt.evaluate(ctx, {"target"})
    if not adapt.all_ok(verdicts):
        return ImportResult(ok=False, dataset_id=None, deduped=False, verdicts=verdicts)
    eng = db.init_db()
    with eng.connect() as c:                               # de-dupe by content hash (cf. openml id)
        existing = c.execute(select(datasets.c.dataset_id)
                             .where(datasets.c.checksum_sha256 == staged.checksum)).first()
    if existing:
        return ImportResult(ok=True, dataset_id=existing[0], deduped=True, verdicts=verdicts)
    meta = infer_metadata(staged.df, target_column=target_column)
    base = f"kaggle:{staged.ref.path}/{staged.file_name}"
    with eng.connect() as c:
        clash = c.execute(select(datasets.c.dataset_id).where(datasets.c.name == base)).first()
    name = base if not clash else f"{base}#{staged.checksum[:8]}"
    uri = objectstore.put("datasets", f"kaggle-{staged.checksum[:12]}.csv", staged.data)
    did = _insert_dataset(eng, name=name, source="kaggle", file_format="csv", storage_uri=uri,
                          checksum_sha256=staged.checksum, status="ready", **meta)
    return ImportResult(ok=True, dataset_id=did, deduped=False, verdicts=verdicts)
