"""US4 runner tests — launch lifecycle + job-result ingestion, with Docker mocked/absent."""
import pytest


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    from storage import db, seed
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    db._engine = None
    seed.seed_catalog()
    yield
    db._engine = None


def test_list_runnable_only_integrated(seeded):
    from storage import runner
    names = runner.list_runnable()
    assert "flaml" in names              # seeded integrated
    assert "autosklearn" not in names    # seeded available (image not pulled)


def test_launch_docker_absent_marks_failed(seeded, monkeypatch):
    from storage import runner
    monkeypatch.setattr(runner, "_docker_available", lambda: False)
    tr_id, status = runner.launch("flaml")
    assert status == "failed" and tr_id is not None
    jobs = runner.list_jobs()
    row = jobs[jobs["training_run_id"] == tr_id].iloc[0]
    assert row["status"] == "failed" and row["framework"] == "flaml"


def test_launch_not_integrated_returns_failed(seeded, monkeypatch):
    from storage import runner
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)  # never spawn a real run
    assert runner.launch("autosklearn")[1] == "failed"   # available, no image → cannot run


def test_launch_starts_worker_marks_running(seeded, monkeypatch):
    from storage import runner
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)
    tr_id, status = runner.launch("flaml", constraint="smoke")
    assert status == "running"
    row = runner.list_jobs().iloc[0]
    assert row["status"] == "running" and row["framework"] == "flaml" and row["constraint"] == "smoke"


def _add_dataset(eng, name, **fields):
    from sqlalchemy import insert
    from storage.models import datasets
    with eng.begin() as c:
        return c.execute(insert(datasets).values(name=name, status="ready", **fields)).inserted_primary_key[0]


def test_trainable_datasets_flags_runnability(seeded):
    from storage import db, runner
    eng = db.init_db()
    _add_dataset(eng, "ds_openml", source="openml", openml_task_id=42, task_type="binary")
    _add_dataset(eng, "ds_upload", source="upload", storage_uri="file:///x.csv",
                 target_column="y", task_type="binary")
    _add_dataset(eng, "ds_broken", source="import", task_type="binary")  # no id, no file
    by = {d["name"]: d["runnable"] for d in runner.list_trainable_datasets()}
    assert by["ds_openml"] and by["ds_upload"] and not by["ds_broken"]


def test_launch_links_selected_datasets(seeded, monkeypatch):
    from sqlalchemy import func, select
    from storage import db, runner
    from storage.models import training_run_datasets
    eng = db.init_db()
    d1 = _add_dataset(eng, "ds1", source="openml", openml_task_id=1, task_type="binary")
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)
    tr_id, status = runner.launch("flaml", [d1], "smoke")
    assert status == "running"
    with eng.connect() as c:
        n = c.execute(select(func.count()).select_from(training_run_datasets)
                      .where(training_run_datasets.c.training_run_id == tr_id)).scalar()
    assert n == 1


def test_build_benchmark_openml_entry(seeded, tmp_path, monkeypatch):
    from storage import db, runner
    from storage.models import training_run_datasets
    from sqlalchemy import insert
    eng = db.init_db()
    d1 = _add_dataset(eng, "credit-g", source="openml", openml_task_id=168757, task_type="binary")
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)
    tr_id, _ = runner.launch("flaml", [d1], "smoke")
    monkeypatch.setattr(runner, "USERDIR", str(tmp_path))
    (tmp_path / "benchmarks").mkdir()
    bench, n = runner._build_benchmark(eng, tr_id)
    assert n == 1
    text = (tmp_path / "benchmarks" / f"{bench}.yaml").read_text()
    assert "name: credit-g" in text and "openml_task_id: 168757" in text


def test_list_jobs_ignores_orphan_runs(seeded, monkeypatch):
    """Pre-existing runs with a NULL training_run_id (migrated CSV) must not break list_jobs."""
    from sqlalchemy import insert
    from storage import db, runner
    from storage.models import runs
    eng = db.init_db()
    with eng.begin() as c:                       # an orphan run, like a migrated results.csv row
        c.execute(insert(runs).values(training_run_id=None, status="success", metric="auc"))
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)
    runner.launch("flaml")
    jobs = runner.list_jobs()                    # must not raise on the dtype-mismatched key
    assert jobs.iloc[0]["framework"] == "flaml" and jobs.iloc[0]["runs"] == 0


def test_cancel_running_job_marks_cancelled(seeded, monkeypatch):
    """Stop a running job → status flips to 'cancelled' (not 'failed') and cancel() returns True."""
    from storage import runner
    monkeypatch.setattr(runner, "_docker_available", lambda: True)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)   # don't spawn a real worker
    monkeypatch.setattr(runner, "_container_cli", lambda: "docker")
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: None)     # no real `docker kill`
    tr_id, status = runner.launch("flaml", constraint="smoke")
    assert status == "running"
    assert runner.cancel(tr_id) is True
    jobs = runner.list_jobs()
    assert jobs[jobs["training_run_id"] == tr_id].iloc[0]["status"] == "cancelled"


def test_cancel_finished_job_is_noop(seeded, monkeypatch):
    """A job that already finished keeps its real result — cancel() returns False, no relabel."""
    from storage import runner
    monkeypatch.setattr(runner, "_docker_available", lambda: False)         # job ends up 'failed'
    monkeypatch.setattr(runner, "_container_cli", lambda: "docker")
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: None)
    tr_id, status = runner.launch("flaml")
    assert status == "failed"
    assert runner.cancel(tr_id) is False                                    # not running → nothing to cancel
    jobs = runner.list_jobs()
    assert jobs[jobs["training_run_id"] == tr_id].iloc[0]["status"] == "failed"


def test_reap_stale_running_job(seeded, monkeypatch):
    """A 'running' job older than RUN_TIMEOUT+grace (worker died) is auto-failed; a fresh one isn't."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import insert, select
    from storage import db, runner
    from storage.models import training_runs
    eng = db.init_db()
    old = datetime.now(timezone.utc) - timedelta(seconds=runner.RUN_TIMEOUT + 600)
    fresh = datetime.now(timezone.utc)
    with eng.begin() as c:
        stale = c.execute(insert(training_runs).values(status="running", started_at=old)).inserted_primary_key[0]
        live = c.execute(insert(training_runs).values(status="running", started_at=fresh)).inserted_primary_key[0]
    reaped = runner.reap_stale_jobs()
    assert stale in reaped and live not in reaped
    with eng.connect() as c:
        sts = dict(c.execute(select(training_runs.c.training_run_id, training_runs.c.status)).all())
    assert sts[stale] == "failed" and sts[live] == "running"


def test_ingest_job_links_runs(seeded, tmp_path, monkeypatch):
    """A produced results.csv is ingested into `runs`, tagged with the job id."""
    import pandas as pd
    from sqlalchemy import func, select
    from storage import db, runner
    from storage.models import runs
    csv = tmp_path / "results.csv"
    pd.DataFrame([{
        "id": "openml.org/t/1", "task": "kc1", "framework": "flaml", "constraint": "smoke",
        "fold": 0, "type": "binary", "result": 0.83, "metric": "auc", "mode": "local",
        "version": "2.3.6", "utc": "2026-06-24", "duration": 12.0, "training_duration": 10.0,
        "predict_duration": 0.4, "models_count": 5, "seed": 1, "info": None, "acc": 0.8, "auc": 0.83,
    }]).to_csv(csv, index=False)
    monkeypatch.setattr(runner, "_docker_available", lambda: False)  # never spawn a real run
    eng = db.init_db()
    tr_id, _ = runner.launch("flaml")          # docker absent → row exists, status failed
    n = runner._ingest_job(eng, tr_id, str(csv))
    assert n == 1
    with eng.connect() as c:
        cnt = c.execute(select(func.count()).select_from(runs)
                        .where(runs.c.training_run_id == tr_id)).scalar()
    assert cnt == 1
