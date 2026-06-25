"""Phase 0/US7 storage tests — relational ingest (CSV → SQLAlchemy) → repo roundtrip.

Each test points the engine at a throwaway SQLite file via DATABASE_URL (works identically
on Postgres), so no container is needed.
"""
import os

import pandas as pd
import pytest

from analysis.load_results import load_results

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Isolate each test on its own SQLite file via the engine factory."""
    from storage import db
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    db._engine = None
    yield
    db._engine = None


def test_migrate_then_repo_matches_csv(tmp_db):
    from storage import migrate, repo
    n = migrate.migrate(FIXTURE)
    assert n > 0
    df_db = repo.load(csv_fallback=FIXTURE)
    df_csv = load_results(FIXTURE)
    assert len(df_db) == len(df_csv)
    assert set(df_db["framework"]) == set(df_csv["framework"])
    assert df_db["success"].dtype == bool
    assert int(df_db["success"].sum()) == int(df_csv["success"].sum())


def test_db_ranking_equals_csv_ranking(tmp_db):
    """SC-009 + the score-as-TEXT regression guard, now over the relational store."""
    from storage import migrate, repo
    from analysis.rankings import average_ranks
    migrate.migrate(FIXTURE)
    o_db, _ = average_ranks(repo.load(csv_fallback=FIXTURE))
    o_csv, _ = average_ranks(load_results(FIXTURE))
    pd.testing.assert_frame_equal(
        o_db.sort_values("framework").reset_index(drop=True),
        o_csv.sort_values("framework").reset_index(drop=True),
    )


def test_score_is_numeric(tmp_db):
    from storage import migrate, repo
    migrate.migrate(FIXTURE)
    assert pd.api.types.is_numeric_dtype(repo.load(csv_fallback=FIXTURE)["score"])


def test_catalog_seeded_with_fk(tmp_db):
    """Methods/datasets are seeded and runs reference them (relational, not flat)."""
    from sqlalchemy import func, select
    from storage import db, migrate
    from storage.models import datasets, methods, runs
    migrate.migrate(FIXTURE)
    eng = db.init_db()
    with eng.connect() as c:
        assert c.execute(select(func.count()).select_from(methods)).scalar() >= 3
        assert c.execute(select(func.count()).select_from(datasets)).scalar() >= 3
        # every run links to a real method + dataset
        orphan = c.execute(select(func.count()).select_from(runs)
                           .where(runs.c.method_id.is_(None))).scalar()
        assert orphan == 0


def test_repo_falls_back_to_csv_without_db(tmp_db):
    """Empty DB (no ingest) → repo reads the CSV fallback."""
    from storage import repo
    assert repo.source(csv_fallback=FIXTURE) == "csv"
    assert len(repo.load(csv_fallback=FIXTURE)) == len(load_results(FIXTURE))


def test_migrate_idempotent(tmp_db):
    from storage import migrate, repo
    n1 = migrate.migrate(FIXTURE)
    n2 = migrate.migrate(FIXTURE)
    assert n1 == n2
    assert len(repo.load(csv_fallback=FIXTURE)) == n1  # rebuilt, not duplicated


def test_reruns_preserved_no_dedup(tmp_db, tmp_path):
    """A re-run (same key, success + failure) keeps BOTH rows so analysis can aggregate."""
    from storage import migrate, repo
    csv = tmp_path / "rerun.csv"
    csv.write_text(
        "id,task,framework,fold,type,result,metric,predict_duration,info\n"
        "t1,credit-g,flaml,0,binary,0.87,auc,0.1,\n"
        "t1,credit-g,flaml,0,binary,,auc,,boom\n"
        "t1,credit-g,RandomForest,0,binary,0.80,auc,0.2,\n"
    )
    migrate.migrate(str(csv))
    df = repo.load(csv_fallback=str(csv))
    assert len(df) == 3
    assert int(df["success"].sum()) == 2
