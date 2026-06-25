"""Ingest an AMLB results CSV into the relational store (FR-017).

Resolves foreign keys: seeds `methods` / `datasets` / `constraints` by name (if absent),
then rebuilds `runs` with those ids. Idempotent — re-running replaces the `runs` rows
(mirrors the CSV; analysis aggregates over status='success'). Uploaded datasets and other
catalog rows are preserved (get-or-create by name).

CLI:  python -m storage.migrate [results.csv]
"""
from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import delete, insert, select

from analysis.load_results import load_results
from storage import db
from storage.models import constraints, datasets, methods, runs

BASELINES = {"constantpredictor", "RandomForest", "TunedRandomForest"}
METRIC_COLS = ["acc", "auc", "balacc", "logloss", "mae", "r2", "rmse"]


def _num(v):
    return None if pd.isna(v) else float(v)


def _int(v):
    return None if pd.isna(v) else int(v)


def _failure_category(info):
    s = str(info or "").lower()
    if "memory" in s or "oom" in s:
        return "failure_memory"
    if "timeout" in s or "time limit" in s or "exceeded" in s:
        return "failure_time"
    if ("class" in s and "split" in s) or "unsupported" in s:
        return "failure_data"
    return "failure_implementation"


def _get_or_create(conn, table, name, **extra):
    pk = list(table.primary_key.columns)[0]
    found = conn.execute(select(pk).where(table.c.name == name)).first()
    if found:
        return found[0]
    return conn.execute(insert(table).values(name=name, **extra)).inserted_primary_key[0]


def migrate(csv_path=None, eng=None):
    """Rebuild `runs` from `csv_path`. Returns rows written."""
    csv_path = csv_path or db.DEFAULT_CSV
    eng = db.init_db(eng)
    from storage.seed import seed_catalog
    seed_catalog(eng)  # rich methods/constraints/compute before resolving FKs
    df = load_results(csv_path)
    has_constraint = "constraint" in df.columns

    with eng.begin() as conn:
        conn.execute(delete(runs))  # idempotent rebuild
        m_ids = {fw: _get_or_create(conn, methods, fw,
                                     kind="baseline" if fw in BASELINES else "automl")
                 for fw in df["framework"].dropna().unique()}
        d_ids = {}
        for task, sub in df.groupby("task"):
            ttype = sub["type"].iloc[0] if "type" in sub.columns else None
            d_ids[task] = _get_or_create(conn, datasets, task, source="import", task_type=ttype)
        c_ids = {}
        if has_constraint:
            for cn in df["constraint"].dropna().unique():
                c_ids[cn] = _get_or_create(conn, constraints, cn)

        rows = []
        for _, r in df.iterrows():
            metrics = {k: float(r[k]) for k in METRIC_COLS
                       if k in df.columns and not pd.isna(r.get(k))}
            rows.append(dict(
                dataset_id=d_ids.get(r["task"]),
                method_id=m_ids.get(r["framework"]),
                constraint_id=c_ids.get(r.get("constraint")) if has_constraint else None,
                fold=_int(r.get("fold")),
                metric=None if pd.isna(r.get("metric")) else str(r["metric"]),
                result=_num(r.get("result_num")),
                score=_num(r.get("score")),
                status="success" if bool(r["success"]) else _failure_category(r.get("info")),
                training_duration=_num(r.get("training_duration")),
                predict_duration=_num(r.get("predict_duration")),
                models_count=_int(r.get("models_count")),
                seed=_int(r.get("seed")),
                framework_version=None if pd.isna(r.get("version")) else str(r["version"]),
                metrics=metrics or None,
            ))
        if rows:
            conn.execute(insert(runs), rows)
    return len(df)


def main(argv):
    csv = argv[1] if len(argv) > 1 else db.DEFAULT_CSV
    n = migrate(csv)
    print(f"ingested {n} rows: {csv} → {db.database_url()} (relational: runs + catalog)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
