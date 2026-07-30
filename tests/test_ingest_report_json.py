"""Phase 4 bridge — ingest a run_automl.py `reports/run_*.json` into the `runs` table.

Offline: a throwaway SQLite engine via DATABASE_URL + a hand-built fixture JSON (no live
Kaggle / no committed report needed). Verifies the mapping, score orientation, memory
capture, failure handling, and re-import idempotency.
"""
import json

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    from storage import db
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    db._engine = None
    yield
    db._engine = None


def _fixture_report(tmp_path):
    """A 2-dataset × 2-framework run with one lower-is-better metric and one failure row."""
    report = {
        "run_id": "test_run",
        "time_budget": 60,
        "frameworks": ["flaml", "autogluon"],
        "started_at": "2026-07-02T00:00:00",
        "results": [
            {"dataset": "breast_cancer", "framework": "flaml", "status": "done",
             "task": "classification", "metric_name": "auc",
             "metric_score": 0.99, "metric_score_raw": 0.99, "metric_direction": "higher_is_better",
             "best_model": "catboost", "resource_usage": {"duration_s": 68.2, "peak_memory_mb": 218.2},
             "error": None},
            {"dataset": "california_housing", "framework": "flaml", "status": "done",
             "task": "regression", "metric_name": "rmse",
             "metric_score": -0.47, "metric_score_raw": 0.47, "metric_direction": "lower_is_better",
             "best_model": "lgbm", "resource_usage": {"duration_s": 55.0, "peak_memory_mb": 120.7},
             "error": None},
            {"dataset": "breast_cancer", "framework": "autogluon", "status": "error",
             "task": "classification", "metric_name": "auc",
             "metric_score": None, "metric_score_raw": None, "metric_direction": "higher_is_better",
             "best_model": None, "resource_usage": {"duration_s": 3.0, "peak_memory_mb": 15.9},
             "error": "Out of memory: container killed"},
        ],
    }
    p = tmp_path / "run_test.json"
    p.write_text(json.dumps(report))
    return str(p)


def test_ingest_maps_rows_scores_and_links(env, tmp_path):
    from storage import ingest, repo
    summary = ingest.ingest_report_json(_fixture_report(tmp_path))
    assert summary["inserted"] == 3
    assert summary["constraint"] == "60s"

    df = repo.load()
    assert len(df) == 3
    assert set(df["framework"]) == {"flaml", "autogluon"}
    assert set(df["task"]) == {"breast_cancer", "california_housing"}
    # budget flows through as the constraint name
    assert set(df["constraint"].dropna()) == {"60s"}

    # result and score are both stored already-oriented (higher = better) to match the
    # load_results / repo.load contract: rmse stays negative, auc positive.
    bc = df[(df["task"] == "breast_cancer") & (df["framework"] == "flaml")].iloc[0]
    ca = df[df["task"] == "california_housing"].iloc[0]
    assert bc["result"] == pytest.approx(0.99) and bc["score"] == pytest.approx(0.99)
    assert ca["result"] == pytest.approx(-0.47) and ca["score"] == pytest.approx(-0.47)


def test_ingest_task_type_and_memory(env, tmp_path):
    from sqlalchemy import select
    from storage import db, ingest, repo
    from storage.models import datasets, runs
    ingest.ingest_report_json(_fixture_report(tmp_path))

    # task_type inferred from metric when no local dataset file exists (auc→binary, rmse→regression)
    cat = repo.list_datasets().set_index("name")
    assert cat.loc["breast_cancer", "task_type"] == "binary"
    assert cat.loc["california_housing", "task_type"] == "regression"

    # peak_memory_mb rides in the runs.metrics JSON (source for Phase 6 Hình 9)
    eng = db.init_db()
    with eng.connect() as c:
        mems = [row[0] for row in c.execute(select(runs.c.metrics)).all()]
    peaks = [m.get("peak_memory_mb") for m in mems if m]
    assert 218.2 in peaks and 120.7 in peaks


def test_failure_row_categorized_and_excluded(env, tmp_path):
    from analysis import failures
    from storage import ingest, repo
    ingest.ingest_report_json(_fixture_report(tmp_path))
    df = repo.load()
    failed = df[~df["success"]]
    assert len(failed) == 1
    assert failed.iloc[0]["status"] == "failure_memory"          # coarse label on runs.status
    # failed run has no score → excluded from any ranking downstream
    assert failed.iloc[0]["score"] != failed.iloc[0]["score"]    # NaN

    # and it reaches the Evaluation failure chart correctly (via the `info` column repo.load
    # now exposes) — not silently bucketed as "unknown".
    cats = failures.by_category(df).set_index("failure_category")["n"]
    assert cats["memory"] == 1 and cats["unknown"] == 0


def test_reimport_is_idempotent(env, tmp_path):
    from storage import ingest, repo
    path = _fixture_report(tmp_path)
    ingest.ingest_report_json(path)
    second = ingest.ingest_report_json(path)
    assert second["inserted"] == 0 and second["skipped_duplicate"] == 3
    assert len(repo.load()) == 3                                 # no duplicate rows
