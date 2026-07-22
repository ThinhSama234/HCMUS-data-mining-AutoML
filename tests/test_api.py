"""Spec 007 — backend API, hermetic. FastAPI TestClient over a temp SQLite seeded from the results
fixture; Kaggle uses the fake seam; no network (FR-013 / SC-005)."""
from __future__ import annotations

import os

import pytest

from storage import kaggle_client
from storage.kaggle_client import FileInfo

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")
URL = "https://www.kaggle.com/datasets/owner/slug"
SINGLE = "f1,f2,f3,label\n" + "\n".join(f"{i},{i * 2},{i % 3},{i % 2}" for i in range(20)) + "\n"


class FakeKaggle:
    def __init__(self, files, blobs=None):
        self._files, self._blobs = files, blobs or {}

    def list_files(self, ref):
        return self._files

    def file_size(self, ref, name):
        return next((f.size_bytes for f in self._files if f.name == name), None)

    def download_file(self, ref, name, max_bytes):
        return self._blobs[name]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from storage import db, migrate, objectstore
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.delenv("S3_ENDPOINT", raising=False)   # force the local object store (no MinIO)
    monkeypatch.setattr(objectstore, "_LOCAL_ROOT", str(tmp_path / "obj"))
    db._engine = None
    migrate.migrate(FIXTURE)                       # seed methods + datasets + runs
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as c:
        yield c
    db._engine = None
    kaggle_client.set_client(None)


# --- US1: read parity + pagination + error shape ---------------------------

def test_datasets_read_parity(client):
    from storage import repo
    body = client.get("/api/v1/datasets").json()
    assert body["total"] == len(repo.list_datasets())
    assert {i["name"] for i in body["items"]} == set(repo.list_datasets()["name"])


def test_pagination_clamps_and_offsets(client):
    one = client.get("/api/v1/datasets?limit=1&offset=0").json()
    assert len(one["items"]) == 1 and one["limit"] == 1
    assert client.get("/api/v1/datasets?limit=9999").json()["limit"] == 200   # clamped


def test_unknown_id_error_shape(client):
    r = client.get("/api/v1/datasets/999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_methods_and_results_read(client):
    assert "items" in client.get("/api/v1/methods").json()
    assert "items" in client.get("/api/v1/results").json()


# --- US2: drive the workflow ------------------------------------------------

def test_training_options_and_bad_launch(client):
    opt = client.get("/api/v1/training/options").json()
    assert set(opt) == {"methods", "constraints", "datasets"}
    r = client.post("/api/v1/training-runs", json={"method": "does-not-exist"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_input"


def test_cost_estimate(client):
    r = client.post("/api/v1/cost/estimate", json={"datasets": 2, "frameworks": 3})
    body = r.json()
    assert r.status_code == 200 and body["total_runs"] == 2 * 3 * body["folds"]


def test_integrate_returns_handle(client):
    r = client.post("/api/v1/methods/RandomForest/integrate")
    assert r.status_code == 202
    assert r.json()["kind"] == "integration" and "poll" in r.json()


def test_kaggle_import_via_api(client, monkeypatch):
    monkeypatch.setattr(kaggle_client, "credentials_present", lambda: True)
    kaggle_client.set_client(FakeKaggle([FileInfo("data.csv", len(SINGLE))],
                                        {"data.csv": SINGLE.encode()}))
    assert client.post("/api/v1/datasets/kaggle/list", json={"url": URL}).json()["ok"]
    imp = client.post("/api/v1/datasets/kaggle/import",
                      json={"url": URL, "file_name": "data.csv", "target_column": "label"})
    assert imp.status_code == 200 and imp.json()["dataset_id"]
    # competition URL → rejected
    comp = client.post("/api/v1/datasets/kaggle/import",
                       json={"url": "https://www.kaggle.com/competitions/titanic",
                             "file_name": "x.csv", "target_column": "y"})
    assert comp.status_code == 422 and comp.json()["error"]["code"] == "rule_rejected"


def test_bad_upload_is_invalid_input(client):
    r = client.post("/api/v1/datasets/upload",
                    files={"file": ("bad.csv", b"\x00\x01 not a csv", "text/csv")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_input"


# --- US3: discoverable, versioned, no secrets ------------------------------

def test_version_and_openapi(client):
    assert client.get("/api/v1/version").json()["api"] == "v1"
    spec = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/datasets" in spec["paths"] and "/api/v1/cost/estimate" in spec["paths"]


def test_no_secret_leak(client, monkeypatch):
    monkeypatch.setenv("KAGGLE_KEY", "supersecret-xyz")
    dburl = os.environ.get("DATABASE_URL", "")
    for path in ("/api/v1/openapi.json", "/api/v1/datasets", "/api/v1/methods"):
        text = client.get(path).text
        assert "supersecret-xyz" not in text
        assert dburl not in text
