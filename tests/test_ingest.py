"""US8 ingestion tests — upload → object store + datasets row (local fallback, no MinIO)."""
import os

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    from storage import db, objectstore
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    monkeypatch.delenv("S3_ENDPOINT", raising=False)            # → local object-store fallback
    monkeypatch.setattr(objectstore, "_LOCAL_ROOT", str(tmp_path / "obj"))
    db._engine = None
    yield
    db._engine = None


def test_infer_metadata_binary_and_regression():
    import pandas as pd
    from storage.ingest import infer_metadata
    binary = pd.DataFrame({"f1": range(10), "f2": range(10), "y": [0, 1] * 5})
    m = infer_metadata(binary)
    assert m["task_type"] == "binary" and m["n_classes"] == 2 and m["n_features"] == 2
    assert abs(m["minority_fraction"] - 0.5) < 1e-9
    reg = pd.DataFrame({"f1": range(50), "target": [i * 1.5 for i in range(50)]})
    assert infer_metadata(reg)["task_type"] == "regression"


def test_ingest_upload_roundtrip(env):
    from storage import ingest, repo, objectstore
    csv = b"a,b,label\n1,2,0\n3,4,1\n5,6,0\n7,8,1\n"
    did = ingest.ingest_upload(csv, "tiny.csv")
    assert did

    cat = repo.list_datasets()
    row = cat[cat["dataset_id"] == did].iloc[0]
    assert row["name"] == "tiny.csv" and row["source"] == "upload"
    assert row["task_type"] == "binary" and int(row["n_features"]) == 2
    # file actually landed in the (local) object store and is retrievable
    assert objectstore.get(row["storage_uri"]) == csv


def test_ingest_upload_rejects_malformed_no_row(env):
    from storage import ingest, repo
    with pytest.raises(ValueError):
        ingest.ingest_upload(b"only_one_column\n1\n2\n", "bad.csv")   # no target column
    assert repo.list_datasets().empty            # nothing written on rejection
