"""Dataset ingestion (FR-015, FR-016) — file → object store, metadata → datasets table.

Both flows return the new dataset_id; the dataset is then selectable for training (SC-008).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import uuid
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import insert, select

from storage import adapt, db, kaggle_client, objectstore
from storage.models import constraints, datasets, methods, runs


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


def ingest_openml(task_id: int, alias: str = None) -> int:
    """Fetch an OpenML task's dataset → object store (parquet) + a datasets row. FR-016.

    ``alias`` is an optional friendly display name used instead of OpenML's cryptic name
    (e.g. show `breast_cancer` rather than `wdbc`); it becomes the dataset's ``name``.
    """
    import openml
    task = openml.tasks.get_task(int(task_id))
    ds = task.get_dataset()
    X, y, _, _ = ds.get_data(target=task.target_name)
    frame = X.copy()
    frame[task.target_name] = y
    # some OpenML datasets (e.g. covertype) return SparseDtype columns → pyarrow/parquet can't
    # write them ("Sparse pandas data … not supported"). Densify before profiling + storing.
    _sparse = [c for c in frame.columns if isinstance(frame[c].dtype, pd.SparseDtype)]
    for c in _sparse:
        frame[c] = frame[c].sparse.to_dense()
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
    name = (alias or "").strip() or ds.name
    return _insert_dataset(eng, name=name, source="openml", openml_task_id=int(task_id),
                           file_format="parquet", storage_uri=uri, status="ready", **meta)


# --- Report-JSON ingestion (Phase 4 bridge) --------------------------------
# The report's real results come from a separate harness (`scripts/run_automl.py` →
# `reports/run_*.json`), NOT the AMLB console. This bridges that output into the console's
# `runs` table so the Evaluation views (which read `storage.repo.load()`) render real data.
# Reuses the same get-or-create + coercion helpers as the live-run ingest (`storage.migrate`),
# so both ingest paths stay consistent (INV-2).

# metric_name → task_type hint, used only when no local dataset file is available to infer from.
_REGRESSION_METRICS = {"rmse", "mae", "mse", "r2", "rmsle"}
_BINARY_METRICS = {"auc"}


def _task_type_from(report_task, metric):
    """Best-effort task_type (binary|multiclass|regression) from the report's metric/task."""
    m = (metric or "").lower()
    if m in _REGRESSION_METRICS:
        return "regression"
    if m in _BINARY_METRICS:
        return "binary"
    if m in {"acc", "accuracy", "logloss", "log_loss", "balacc", "bac"}:
        return "multiclass"
    t = (report_task or "").lower()
    return "regression" if t == "regression" else "multiclass" if t == "classification" else None


def _dataset_meta_from_file(name):
    """Characteristics from a local ``dataset/<name>/train.csv`` via infer_metadata, or None.

    The report pipeline ships the raw dataset files, so when one is present we get real
    n_instances / n_features / minority_fraction / task_type instead of NULLs.
    """
    base = os.path.join(db.REPO_ROOT, "dataset", name)
    csv_path = os.path.join(base, "train.csv")
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None
    target = None
    meta_path = os.path.join(base, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as mf:
                target = json.load(mf).get("label")
        except Exception:
            target = None
    try:
        return infer_metadata(df, target_column=target)
    except Exception:
        return None


def ingest_report_json(path, eng=None):
    """Ingest a ``reports/run_*.json`` (from ``scripts/run_automl.py``) into the ``runs`` table.

    Maps each result → a runs row, resolving datasets/methods/constraints by name
    (get-or-create). Datasets get real characteristics from a local ``dataset/<name>/train.csv``
    when present. Idempotent on ``(method, dataset, constraint, fold)`` so re-import is safe.
    Returns a summary dict.
    """
    with open(path) as f:
        return _ingest_report(json.load(f), eng)


def ingest_report_bytes(data, eng=None):
    """Ingest raw JSON bytes/str (e.g. a console upload). See ``ingest_report_json``."""
    return _ingest_report(json.loads(data), eng)


def _ingest_report(report, eng=None):
    from storage.migrate import BASELINES, _failure_category, _get_or_create, _num

    results = report.get("results", []) or []
    budget = report.get("time_budget")
    eng = eng or db.init_db()

    inserted = skipped = 0
    m_cache, d_cache, seen = {}, {}, set()
    with eng.begin() as conn:
        cname = f"{int(budget)}s" if budget is not None else "unknown"
        cid = _get_or_create(conn, constraints, cname,
                             max_runtime_seconds=int(budget) if budget is not None else None)
        rows = []
        for r in results:
            fw, ds = r.get("framework"), r.get("dataset")
            if not fw or not ds:
                continue
            if fw not in m_cache:
                m_cache[fw] = _get_or_create(conn, methods, fw,
                                             kind="baseline" if fw in BASELINES else "automl")
            if ds not in d_cache:
                meta = _dataset_meta_from_file(ds) or {}
                meta.setdefault("task_type", _task_type_from(r.get("task"), r.get("metric_name")))
                d_cache[ds] = _get_or_create(conn, datasets, ds, source="report", **meta)

            # dedupe on (method, dataset, constraint, fold=0) — both across re-imports (query the
            # committed rows) and within this file (`seen`, since buffered rows aren't flushed yet).
            fold = 0
            key = (m_cache[fw], d_cache[ds], cid, fold)
            dup = key in seen or conn.execute(select(runs.c.run_id).where(
                (runs.c.method_id == m_cache[fw]) & (runs.c.dataset_id == d_cache[ds]) &
                (runs.c.constraint_id == cid) & (runs.c.fold == fold))).first()
            if dup:
                skipped += 1
                continue
            seen.add(key)

            metric = (r.get("metric_name") or "").lower() or None
            raw = r.get("metric_score_raw", r.get("metric_score"))
            # `metric_score` is already direction-normalized (higher = better) by the harness,
            # matching analysis.load_results' `score`; store it verbatim for INV-2 consistency.
            score = r.get("metric_score")
            err = r.get("error")
            ok = r.get("status") == "done" and err is None and raw is not None
            ru = r.get("resource_usage") or {}
            metrics = {k: v for k, v in (
                ("peak_memory_mb", ru.get("peak_memory_mb")),
                ("duration_s", ru.get("duration_s")),
                ("best_model", r.get("best_model")),
                ("time_budget", budget),
            ) if v is not None}
            rows.append(dict(
                dataset_id=d_cache[ds], method_id=m_cache[fw], constraint_id=cid, fold=fold,
                metric=metric,
                # store the already-oriented value in BOTH result and score so `repo.load()`'s
                # `result_num` matches the AMLB/load_results contract (rmse stays negative).
                result=None if score is None else float(score),
                score=None if score is None else float(score),
                status="success" if ok else _failure_category(err),
                training_duration=_num(ru.get("duration_s")) if ru.get("duration_s") is not None else None,
                metrics=metrics or None,
                error_message=None if err is None else str(err),
            ))
            inserted += 1
        if rows:
            conn.execute(insert(runs), rows)
    return {"inserted": inserted, "skipped_duplicate": skipped,
            "datasets": len(d_cache), "methods": len(m_cache), "constraint": cname}


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
