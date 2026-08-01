"""Data-access — DB-first, CSV-fallback. Returns the SAME tidy frame as analysis.load_results
(columns: framework, task, type, metric, result, result_num, success, score, predict_duration,
training_duration, …) so analysis/console are unchanged whether the source is
PostgreSQL, SQLite, or the raw CSV (FR-014). See contracts/schema.md read contract.
"""
from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import func, select

from storage import db
from storage.models import constraints, datasets, methods, runs


def _list(table, order=None):
    try:
        eng = db.init_db()
        stmt = select(table)
        if order is not None:
            stmt = stmt.order_by(order)
        with eng.connect() as c:
            return pd.read_sql(stmt, c)
    except Exception:
        return pd.DataFrame()


def list_datasets():
    """All catalog datasets (US8) — empty frame if none/unavailable."""
    return _list(datasets, datasets.c.created_at.desc())


def list_methods():
    return _list(methods, methods.c.method_id)


def get_method(name):
    """Single method row as a dict (None if absent) — cheap, for the detail/poll view."""
    try:
        eng = db.init_db()
        with eng.connect() as c:
            df = pd.read_sql(select(methods).where(methods.c.name == name), c)
        return df.iloc[0].to_dict() if not df.empty else None
    except Exception:
        return None


def list_instances():
    from storage.models import compute_instances
    return _list(compute_instances, compute_instances.c.instance_id)


def _row_count():
    try:
        eng = db.init_db()
        with eng.connect() as c:
            return c.execute(select(func.count()).select_from(runs)).scalar() or 0
    except Exception:
        return 0


def source(csv_fallback=None):
    """'db' if the runs table has rows, else 'csv' if the CSV exists, else 'none'."""
    csv_fallback = csv_fallback or db.DEFAULT_CSV
    if _row_count() > 0:
        return "db"
    return "csv" if os.path.exists(csv_fallback) else "none"


def load(csv_fallback=None):
    """Tidy results frame from the DB if populated, else from the CSV fallback."""
    csv_fallback = csv_fallback or db.DEFAULT_CSV
    if _row_count() > 0:
        eng = db.init_db()
        j = (runs
             .join(datasets, runs.c.dataset_id == datasets.c.dataset_id, isouter=True)
             .join(methods, runs.c.method_id == methods.c.method_id, isouter=True)
             .join(constraints, runs.c.constraint_id == constraints.c.constraint_id, isouter=True))
        stmt = select(
            methods.c.name.label("framework"),
            datasets.c.name.label("task"),
            datasets.c.task_type.label("type"),
            constraints.c.name.label("constraint"),
            constraints.c.max_runtime_seconds.label("budget_s"),   # allocated time budget (Phase 3)
            runs.c.fold, runs.c.metric, runs.c.result, runs.c.score, runs.c.status,
            runs.c.predict_duration, runs.c.training_duration,
            runs.c.models_count, runs.c.seed, runs.c.framework_version.label("version"),
            # expose the stored error as `info` so analysis.failures can classify DB-sourced
            # failures the same way it does CSV rows (which carry an `info` column).
            runs.c.error_message.label("info"),
            # per-run metrics JSON (carries peak_memory_mb for report-ingested runs → Phase 6 memory view).
            runs.c.metrics,
        ).select_from(j)
        with eng.connect() as c:
            df = pd.read_sql(stmt, c)
        df["success"] = df["status"] == "success"
        df["result_num"] = pd.to_numeric(df["result"], errors="coerce")
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        return df

    from analysis.load_results import load_results
    return load_results(csv_fallback)


def rename_dataset(dataset_id, name):
    """Set a dataset's display name (alias). Results map by name, so a rename before a run flows
    straight through to Evaluation/Jobs; after a run, existing runs still link by id."""
    from sqlalchemy import update
    name = (name or "").strip()
    if not name:
        return False
    eng = db.init_db()
    with eng.begin() as c:
        r = c.execute(update(datasets).where(datasets.c.dataset_id == int(dataset_id))
                      .values(name=name))
    return r.rowcount > 0


def set_archived(ids, archived=True):
    """Archive (hide from the Training picker) or un-archive datasets. Non-destructive."""
    from sqlalchemy import update
    ids = [int(i) for i in ids]
    if not ids:
        return 0
    eng = db.init_db()
    with eng.begin() as c:
        r = c.execute(update(datasets).where(datasets.c.dataset_id.in_(ids))
                      .values(archived=bool(archived)))
    return r.rowcount


def delete_datasets(ids):
    """Remove datasets from the catalog, plus any runs/job-links that reference them (FK-safe)."""
    from sqlalchemy import delete
    from storage.models import training_run_datasets
    ids = [int(i) for i in ids]
    if not ids:
        return 0
    eng = db.init_db()
    with eng.begin() as c:
        c.execute(delete(runs).where(runs.c.dataset_id.in_(ids)))
        c.execute(delete(training_run_datasets).where(training_run_datasets.c.dataset_id.in_(ids)))
        r = c.execute(delete(datasets).where(datasets.c.dataset_id.in_(ids)))
    return r.rowcount


def load_job(training_run_id):
    """Per-job tidy results frame — the SAME columns as load(), filtered to one training run.

    Powers the Jobs → job-detail dashboard (a per-job slice of the Evaluation view). DB-only:
    jobs exist only in the DB, so there is no CSV fallback here.
    """
    eng = db.init_db()
    j = (runs
         .join(datasets, runs.c.dataset_id == datasets.c.dataset_id, isouter=True)
         .join(methods, runs.c.method_id == methods.c.method_id, isouter=True)
         .join(constraints, runs.c.constraint_id == constraints.c.constraint_id, isouter=True))
    stmt = select(
        methods.c.name.label("framework"),
        datasets.c.name.label("task"),
        datasets.c.task_type.label("type"),
        datasets.c.size_tier.label("size_tier"),
        constraints.c.name.label("constraint"),
        runs.c.fold, runs.c.metric, runs.c.result, runs.c.score, runs.c.status,
        runs.c.predict_duration, runs.c.training_duration,
        runs.c.error_message.label("info"), runs.c.metrics,
    ).select_from(j).where(runs.c.training_run_id == training_run_id)
    with eng.connect() as c:
        df = pd.read_sql(stmt, c)
    if not df.empty:
        df["success"] = df["status"] == "success"
        df["result_num"] = pd.to_numeric(df["result"], errors="coerce")
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
    return df
