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


def init_db(eng=None):
    """Create all tables if absent (correct DDL per dialect). Returns the engine."""
    eng = eng or engine()
    metadata.create_all(eng)
    return eng
