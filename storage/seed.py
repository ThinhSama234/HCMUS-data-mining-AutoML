"""Seed the reference catalog (T015/T029) — methods / constraints / compute_instances.

- methods: **insert-if-absent** (so a framework's integration_status is preserved across re-seeds;
  integrating an `available` framework won't be reset to `available` later).
- constraints / compute_instances: upsert (config defaults).

Runnable: `python -m storage.seed`. Also called by `storage.migrate` before ingesting results.
"""
from __future__ import annotations

import sys

from sqlalchemy import insert, select, update

from storage import db
from storage.models import compute_instances, constraints, datasets, methods

# AMLB's standard "small" benchmark suite (resources/benchmarks/small.yaml) — classification tasks,
# seeded so they're selectable on the Training page (runnable via openml_task_id). (name, task_id, type)
OPENML_SMALL = [
    ("Australian", 146818, "binary"), ("blood-transfusion", 10101, "binary"),
    ("car", 146821, "multiclass"), ("christine", 168908, "binary"),
    ("cnae-9", 9981, "multiclass"), ("credit-g", 31, "binary"),
    ("dilbert", 168909, "multiclass"), ("fabert", 168910, "multiclass"),
    ("jasmine", 168911, "binary"), ("kc1", 3917, "binary"),
    ("kr-vs-kp", 3, "binary"), ("mfeat-factors", 12, "multiclass"),
    ("phoneme", 9952, "binary"), ("segment", 146822, "multiclass"),
    ("sylvine", 168912, "binary"), ("vehicle", 53, "multiclass"),
]

# Curated — the frameworks/baselines actually used, with real status.
# (name, kind, version, preset, status, docker_image, image_tag, project_url)
CURATED = [
    ("flaml", "automl", "2.3.6", "default", "integrated",
     "automlbenchmark/flaml:1.2.4-v2.1.3", "1.2.4-v2.1.3", "https://github.com/microsoft/FLAML"),
    ("H2OAutoML", "automl", "3.40", "default", "setup_pending",
     "automlbenchmark/h2oautoml:3.40.0.4-v2.1.3", "3.40.0.4-v2.1.3", "https://h2o.ai"),
    ("AutoGluon", "automl", "0.8", "best_quality", "integrated",
     "automlbenchmark/autogluon:0.8.0-v2.1.3", "0.8.0-v2.1.3", "https://auto.gluon.ai"),
    ("RandomForest", "baseline", "1.2", None, "integrated",
     "automlbenchmark/randomforest:1.2.2-v2.1.3", "1.2.2-v2.1.3", "https://scikit-learn.org"),
    ("TunedRandomForest", "baseline", "1.2", None, "failed", None, None, "https://scikit-learn.org"),
    ("constantpredictor", "baseline", "1.0", None, "integrated",
     "automlbenchmark/constantpredictor:stable", "stable", "https://scikit-learn.org"),
]

# Other frameworks AMLB publishes — selectable as `available`. Tags PINNED (resolved once from
# Docker Hub, 2026-06) for reproducible, offline integration; resolve_image still falls back to
# the Hub API for any framework not pinned here. Re-run a fetch to bump versions.
AVAILABLE = [
    ("autosklearn", "0.15.0-v2.1.6"),
    ("gama", "23.0.0-v2.1.3"),
    ("lightautoml", "0.3.7.3-v2.1.3"),
    ("tpot", "0.12.0-v2.1.3"),
    ("mljarsupervised", "0.11.5-v2.1.3"),
    ("autoxgboost", "908631665f4c763d548ed203d48f05fe68613844-v2.0.2"),
    ("hyperoptsklearn", "0.0.3-stable"),
    ("autoweka", "2.6-v2.0.1"),
    ("mlplan", "0.2.4-v2.0.2"),
    ("oboe", "latest-stable"),
    ("ranger", "0.10.1-stable"),
    ("mlr3automl", "826d5241f752b64da835c77616e372866a57c98d-v2.0.5"),
    ("naiveautoml", "0.0.27-v2.1.7"),
]

CONSTRAINTS = [
    ("smoke", 1, 60, 4, {"binary": "auc", "multiclass": "neg_logloss", "regression": "neg_rmse"}),
    ("1h", 10, 3600, 8, {"binary": "auc", "multiclass": "neg_logloss", "regression": "neg_rmse"}),
    ("4h", 10, 14400, 8, {"binary": "auc", "multiclass": "neg_logloss", "regression": "neg_rmse"}),
]

INSTANCES = [
    ("CPU 8-core", 8, 32, None, 0, 0.30),
    ("GPU T4", 8, 32, "T4", 1, 0.95),
    ("GPU A100", 12, 85, "A100", 1, 3.40),
]


def _insert_if_absent(conn, table, name, **fields):
    if conn.execute(select(table.c.name).where(table.c.name == name)).first():
        return  # preserve existing row (e.g. an integrated framework)
    conn.execute(insert(table).values(name=name, **fields))


def _upsert(conn, table, name, **fields):
    if conn.execute(select(table.c.name).where(table.c.name == name)).first():
        conn.execute(update(table).where(table.c.name == name).values(**fields))
    else:
        conn.execute(insert(table).values(name=name, **fields))


def seed_catalog(eng=None):
    eng = db.init_db(eng)
    with eng.begin() as conn:
        for name, kind, ver, preset, status, image, tag, url in CURATED:
            _insert_if_absent(conn, methods, name, kind=kind, version=ver, preset=preset,
                              integration_status=status, docker_image=image, image_tag=tag,
                              project_url=url)
        for name, tag in AVAILABLE:
            _insert_if_absent(conn, methods, name, kind="automl", integration_status="available",
                              image_tag=tag, docker_image=f"automlbenchmark/{name}:{tag}",
                              project_url=f"https://hub.docker.com/r/automlbenchmark/{name}")
        for name, folds, secs, cores, mbt in CONSTRAINTS:
            _upsert(conn, constraints, name, folds=folds, max_runtime_seconds=secs,
                    cores=cores, metric_by_type=mbt)
        for name, vcpus, mem, gpu, ng, rate in INSTANCES:
            _upsert(conn, compute_instances, name, vcpus=vcpus, memory_gb=mem,
                    gpu_type=gpu, gpu_count=ng, rate_per_hour=rate, active=True)
        for name, task_id, ttype in OPENML_SMALL:        # AMLB small suite → trainable datasets
            _insert_if_absent(conn, datasets, name, source="openml", openml_task_id=task_id,
                              task_type=ttype, status="ready")
    return {"methods": len(CURATED) + len(AVAILABLE), "constraints": len(CONSTRAINTS),
            "instances": len(INSTANCES), "datasets": len(OPENML_SMALL)}


def main(argv):
    print("seeded:", seed_catalog())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
