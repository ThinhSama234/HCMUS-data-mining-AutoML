"""Live data access for console pages — DB-first via storage.repo (CSV/SQLite fallback).

Only real data here. Mock fixtures (datasets/methods/jobs/instances/endpoints/budget) were
removed along with the mock-only pages; re-add per-feature when each gets a real backend.
"""
from __future__ import annotations

from console.theme import REPO_ROOT  # noqa: F401  (kept for path setup side effect)

import os

RESULTS_CSV = os.path.join(REPO_ROOT, "results", "results.csv")


def load_results(path=RESULTS_CSV):
    from storage import repo
    return repo.load(csv_fallback=path)


def has_results(path=RESULTS_CSV):
    from storage import repo
    return repo.source(csv_fallback=path) != "none"


def results_source(path=RESULTS_CSV):
    """'db' | 'csv' | 'none' — shown in the UI so the source is explicit."""
    from storage import repo
    return repo.source(csv_fallback=path)
