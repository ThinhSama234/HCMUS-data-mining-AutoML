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
            runs.c.fold, runs.c.metric, runs.c.result, runs.c.score, runs.c.status,
            runs.c.predict_duration, runs.c.training_duration,
            runs.c.models_count, runs.c.seed, runs.c.framework_version.label("version"),
        ).select_from(j)
        with eng.connect() as c:
            df = pd.read_sql(stmt, c)
        df["success"] = df["status"] == "success"
        df["result_num"] = pd.to_numeric(df["result"], errors="coerce")
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        return df

    from analysis.load_results import load_results
    return load_results(csv_fallback)
