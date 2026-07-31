---
phase: 2
title: "Real dataset characteristics from catalog"
status: completed
priority: P1
effort: "0.5-1d"
dependencies: []
---

# Phase 2: Real dataset characteristics from catalog

## Overview

`analysis/by_characteristics.py` currently hardcodes `TASK_META` for only **5 AMLB tasks**
(credit-g/vehicle/Moneyball/churn/Higgs) — none of which are the report's 12 datasets — so the
by-characteristic view (and Bradley-Terry in Phase 3) is blind to the real suite. Replace the
hardcoded map with a lookup from the dataset **catalog**.

**Consistency note (validated 2026-07-30):** the catalog's characteristic columns
(`n_instances / n_features / minority_fraction`) are currently **NULL** even for the 3 existing
rows. **Phase 4 populates them** via `infer_metadata` on import — so this phase's UI value
depends on Phase 4 having run. The code here (the `load_task_meta()` lookup) can still be built
and unit-tested independently with an injected meta source.

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

- [x] By-characteristic view uses catalog data and covers every dataset in the results (no 5-task ceiling).
- [x] `grouped_rankings` public signature unchanged; `explorer.py` and Evaluation untouched.
- [x] Tests pass offline (no live DB required); DB path exercised when available.

## Progress (2026-07-30)

Done + tested (`tests/test_by_characteristics.py`, 8 cases; full suite 96 green):
- `analysis/by_characteristics.load_task_meta(source=None)` — reads characteristics from the
  catalog (`storage.repo.list_datasets`), merged **field-wise over** the curated `TASK_META`
  baseline (a NULL catalog value keeps the curated one; absent → `unknown`). Lazy + guarded:
  importing the module never touches the DB; any failure falls back to `TASK_META`.
- `with_characteristics` / `grouped_rankings` now default `meta=None` → `load_task_meta()`;
  public signatures compatible, so `explorer.py` and `console/views/evaluation.py` are untouched.
- E2E verified: after ingesting the report JSON, `grouped_rankings(by="size_tier")` buckets
  breast_cancer/wine → small, california_housing → medium from real catalog characteristics (no `unknown`).
- Code-review fixes: pinned the two fixture tests with explicit `meta=TASK_META` so they stay
  **hermetic** (the new default reads the live catalog); proven by re-running under a bogus
  `DATABASE_URL`. Hardened the catalog `name` guard against NaN.

## Risk Assessment

- **Risk:** coupling `analysis` → `storage` breaks the "analysis is pure/UI-free" invariant. **Mitigation:** injectable meta source + CSV fallback; DB import guarded and optional.
- **Risk:** result `task` names don't exactly match catalog `name`. **Mitigation:** normalize/trim on join; unmatched → `unknown` (non-fatal), log count.
