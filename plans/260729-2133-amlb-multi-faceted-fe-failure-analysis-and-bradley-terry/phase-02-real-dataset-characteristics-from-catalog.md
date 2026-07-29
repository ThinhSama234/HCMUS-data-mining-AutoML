---
phase: 2
title: "Real dataset characteristics from catalog"
status: pending
priority: P1
effort: "0.5-1d"
dependencies: []
---

# Phase 2: Real dataset characteristics from catalog

## Overview

`analysis/by_characteristics.py` currently hardcodes `TASK_META` for only **5 datasets**,
so the by-characteristic view (and any Bradley-Terry work in Phase 3) is blind to the other
15 datasets in the 20-dataset suite. The dataset catalog already stores the exact
characteristics needed, so replace the hardcoded map with a lookup from the catalog.

## Requirements

- Functional:
  - Source `n_instances`, `n_features`, `n_classes`, `minority_fraction`, `task_type`
    per dataset from the catalog instead of the hardcoded `TASK_META`.
  - Keep the same tier helpers (`size_tier` / `dim_tier` / `balance_tier`) and public
    function signatures so `explorer.py` / Evaluation need no change.
  - Datasets missing from the catalog fall back to `unknown` tiers (current behaviour).
- Non-functional:
  - No breaking change to `grouped_rankings(df, by=...)` contract.
  - Works in both DB modes (Postgres and SQLite fallback) and offline (CSV) — keep a
    file/CSV fallback so `analysis` never hard-depends on a live DB.

## Architecture

Catalog columns (verified in `storage/models.py`, `datasets` table):
`task_type, n_instances, n_features, n_classes, minority_fraction, size_tier`.

Join key: results `task` name ↔ catalog `datasets.name`. Provide a small loader that
returns a `{task_name: (n_instances, n_features, minority_fraction)}` dict — a drop-in
replacement for `TASK_META` — so the rest of `by_characteristics.py` is untouched.

Keep `analysis/` decoupled from `storage/`: the loader accepts an injectable meta source
(default: read from catalog via `storage.repo`; fallback: a cached CSV/JSON snapshot).
`with_characteristics(df, meta=...)` already takes `meta` as a parameter — reuse it.

## Related Code Files

- Modify: `analysis/by_characteristics.py` — replace the constant `TASK_META` with
  `load_task_meta(source=None)` that pulls from the catalog (via `storage.repo`) with a
  CSV/JSON fallback; default `grouped_rankings`/`with_characteristics` to call it lazily.
- Reference (read): `storage/models.py` (datasets table), `storage/repo.py` (dataset query).
- Modify/extend: `tests/` — add a test that a catalog-like meta source flows through
  `grouped_rankings` for >5 datasets; keep an offline fixture so tests need no DB.

## Implementation Steps

1. Add `load_task_meta()` in `analysis/by_characteristics.py`: query the catalog for
   `name, n_instances, n_features, minority_fraction`; return the `TASK_META`-shaped dict.
   Wrap DB access in try/except → fall back to a bundled snapshot / empty dict.
2. Make `with_characteristics` / `grouped_rankings` default `meta=load_task_meta()` (lazy),
   preserving the explicit-`meta` injection path for tests.
3. Keep tiers and thresholds unchanged (small/medium/large, low/mid/high, imbalanced/balanced).
4. Add/adjust tests with an injected multi-dataset meta; run `pytest tests/ -k characteristic -q`.
5. Verify the Evaluation "Ranking by data characteristic" view now covers all datasets present in results.

## Success Criteria

- [ ] By-characteristic view uses catalog data and covers every dataset in the results (no 5-task ceiling).
- [ ] `grouped_rankings` public signature unchanged; `explorer.py` and Evaluation untouched.
- [ ] Tests pass offline (no live DB required); DB path exercised when available.

## Risk Assessment

- **Risk:** coupling `analysis` → `storage` breaks the "analysis is pure/UI-free" invariant. **Mitigation:** injectable meta source + CSV fallback; DB import guarded and optional.
- **Risk:** result `task` names don't exactly match catalog `name`. **Mitigation:** normalize/trim on join; unmatched → `unknown` (non-fatal), log count.
