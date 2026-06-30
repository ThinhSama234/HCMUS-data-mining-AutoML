"""Spec 006 — Kaggle dataset import, hermetic. The Kaggle seam is faked (no network); each test
gets a throwaway SQLite + a temp object store (mirrors the tmp_db pattern in test_storage.py).

Fixtures are inlined as small CSV strings rather than files on disk — the fake client serves bytes,
so the tests stay self-contained and offline.
"""
from __future__ import annotations

import pytest

from storage import kaggle_client
from storage.kaggle_client import FileInfo, KaggleAccessError

URL = "https://www.kaggle.com/datasets/owner/slug"
SINGLE = "f1,f2,f3,label\n" + "\n".join(f"{i},{i * 2},{i % 3},{i % 2}" for i in range(20)) + "\n"
IDCOL = "id,f1,label\n" + "\n".join(f"u{i},{i},{i % 2}" for i in range(20)) + "\n"


class FakeKaggle:
    """A stand-in seam: lists the given FileInfo, serves the given blobs, or raises on listing."""

    def __init__(self, files, blobs=None, raise_on_list=None):
        self._files, self._blobs, self._raise = files, blobs or {}, raise_on_list

    def list_files(self, ref):
        if self._raise:
            raise self._raise
        return self._files

    def file_size(self, ref, name):
        return next((f.size_bytes for f in self._files if f.name == name), None)

    def download_file(self, ref, name, max_bytes):
        data = self._blobs.get(name)
        if data is None:
            raise KaggleAccessError(f"no such file: {name}")
        if len(data) > max_bytes:
            raise KaggleAccessError("file exceeds the size cap")
        return data


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Temp SQLite + temp object store + credentials present + clean seam (reset afterward)."""
    from storage import db, objectstore
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setattr(objectstore, "_LOCAL_ROOT", str(tmp_path / "obj"))
    monkeypatch.setattr(kaggle_client, "credentials_present", lambda: True)
    db._engine = None
    yield
    db._engine = None
    kaggle_client.set_client(None)


def _use(files, blobs=None, raise_on_list=None):
    kaggle_client.set_client(FakeKaggle(files, blobs, raise_on_list))


# --- User Story 1: happy path + dedupe -------------------------------------

def test_happy_path_single_import(env):
    from sqlalchemy import select
    from storage import db, ingest
    from storage.models import datasets
    _use([FileInfo("data.csv", len(SINGLE))], {"data.csv": SINGLE.encode()})

    listing = ingest.kaggle_list(URL)
    assert listing.ok, [v.reason for v in listing.verdicts if not v.ok]
    staged = ingest.kaggle_read(listing.ref, "data.csv")
    assert staged.ok and "label" in staged.columns
    res = ingest.kaggle_import(staged, "label")
    assert res.ok and res.dataset_id and not res.deduped

    eng = db.init_db()
    with eng.connect() as c:
        row = c.execute(select(datasets.c.source, datasets.c.task_type, datasets.c.n_features)
                        .where(datasets.c.dataset_id == res.dataset_id)).first()
    assert row[0] == "kaggle"
    assert row[1] in ("binary", "multiclass", "regression")
    assert row[2] == 3


def test_reimport_dedupes(env):
    from storage import ingest
    _use([FileInfo("data.csv", len(SINGLE))], {"data.csv": SINGLE.encode()})
    listing = ingest.kaggle_list(URL)
    first = ingest.kaggle_import(ingest.kaggle_read(listing.ref, "data.csv"), "label")
    second = ingest.kaggle_import(ingest.kaggle_read(listing.ref, "data.csv"), "label")
    assert second.deduped and second.dataset_id == first.dataset_id


# --- User Story 2: every rejection names its rule --------------------------

def test_r1_competition_url(env):
    from storage import ingest
    _use([])
    listing = ingest.kaggle_list("https://www.kaggle.com/competitions/titanic")
    assert not listing.ok and listing.verdicts[-1].rule_id == "R1-url-shape"


def test_r2_no_credentials(env, monkeypatch):
    from storage import ingest
    monkeypatch.setattr(kaggle_client, "credentials_present", lambda: False)
    _use([FileInfo("data.csv", 10)], {"data.csv": SINGLE.encode()})
    listing = ingest.kaggle_list(URL)
    assert not listing.ok and listing.verdicts[-1].rule_id == "R2-credentials"


def test_r3_unreachable(env):
    from storage import ingest
    _use([], raise_on_list=KaggleAccessError("404 - not found"))
    listing = ingest.kaggle_list(URL)
    assert not listing.ok and listing.verdicts[-1].rule_id == "R3-reachable"


def test_r4_no_tabular_file(env):
    from storage import ingest
    _use([FileInfo("cat.jpg", 100), FileInfo("dog.png", 200)])
    listing = ingest.kaggle_list(URL)
    assert not listing.ok and listing.verdicts[-1].rule_id == "R4-tabular-file"


def test_r5_oversized(env):
    from storage import ingest
    _use([FileInfo("huge.csv", 999 * 1024 * 1024)])
    listing = ingest.kaggle_list(URL)
    assert not listing.ok and listing.verdicts[-1].rule_id == "R5-size"


def test_r7_identifier_target(env):
    from storage import ingest
    _use([FileInfo("d.csv", len(IDCOL))], {"d.csv": IDCOL.encode()})
    listing = ingest.kaggle_list(URL)
    staged = ingest.kaggle_read(listing.ref, "d.csv")
    assert staged.ok
    res = ingest.kaggle_import(staged, "id")
    assert not res.ok and res.verdicts[-1].rule_id == "R7-target-valid"


def test_evaluate_stops_at_first_reject(env):
    from storage import ingest
    listing = ingest.kaggle_list("https://example.com/not-kaggle")
    assert [v.rule_id for v in listing.verdicts] == ["R1-url-shape"]


# --- User Story 3: multi-file pick -----------------------------------------

def test_multi_file_pick(env):
    from storage import ingest
    _use([FileInfo("train.csv", len(SINGLE)), FileInfo("test.csv", 50),
          FileInfo("sample_submission.csv", 30)],
         {"train.csv": SINGLE.encode()})
    listing = ingest.kaggle_list(URL)
    assert listing.ok
    tabular = [f.name for f in listing.files if f.name.endswith(".csv")]
    assert len(tabular) == 3
    staged = ingest.kaggle_read(listing.ref, "train.csv")
    assert staged.ok and "label" in staged.columns
    assert ingest.kaggle_import(staged, "label").ok


# --- smoke: the Datasets page renders with the Kaggle control --------------

def test_datasets_page_renders_with_kaggle_control(env):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file("console/views/datasets.py", default_timeout=60).run()
    assert not app.exception
    assert any("Kaggle" in (t.label or "") for t in app.text_input)
