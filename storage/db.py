"""Engine factory — `DATABASE_URL` → PostgreSQL (docker), else local SQLite (dev/test).

Lowest layer: no console/streamlit imports. The DB is a derived store of the results CSV;
safe to rebuild. `init_db()` creates the relational schema (storage/models.py) on first use.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine

from storage.models import metadata

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_PATH = os.path.join(REPO_ROOT, "console.db")
DEFAULT_CSV = os.path.join(REPO_ROOT, "results", "results.csv")

# Load .env (DATABASE_URL, S3_*) once, without clobbering real env (docker-compose sets its own).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, ".env"), override=False)
except ModuleNotFoundError:
    pass

_engine = None


def database_url():
    """Postgres when DATABASE_URL is set (docker-compose); otherwise local SQLite (no container)."""
    return os.environ.get("DATABASE_URL") or f"sqlite:///{SQLITE_PATH}"


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), future=True)
    return _engine


_migrated = False


def init_db(eng=None):
    """Create all tables if absent (correct DDL per dialect). Returns the engine."""
    global _migrated
    eng = eng or engine()
    metadata.create_all(eng)
    if not _migrated:
        _add_missing_columns(eng)   # columns added after a DB was first created (create_all won't ALTER)
        _migrated = True
    return eng


def _add_missing_columns(eng):
    """Idempotently add newer columns to pre-existing tables (portable across sqlite/postgres)."""
    from sqlalchemy import inspect, text
    try:
        cols = {c["name"] for c in inspect(eng).get_columns("datasets")}
    except Exception:
        return
    if "archived" not in cols:
        with eng.begin() as c:
            c.execute(text("ALTER TABLE datasets ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE"))
