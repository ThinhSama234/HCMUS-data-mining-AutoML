---
phase: 5
title: "Expand dataset suite across tiers"
status: pending
priority: P3
effort: "1-2d (mostly data + compute)"
dependencies: []
---

# Phase 5: Expand dataset suite across tiers

## Overview

Close checklist §2: a credible benchmark needs ~10–20 datasets spanning the three task types and the
size / dimensionality / class-balance tiers — not 3–4. This is mostly a **data-collection + run** task
on top of the existing Kaggle-import + catalog + AMLB machinery; the code to import, characterize, and
run already exists.

## Requirements

- Functional:
  - Catalog holds **≥10 datasets** (target 12–20) spanning: 3 task types (binary / multiclass /
    regression) × the size tiers (small <2k / medium 2k–50k / large >50k) × the dim + balance tiers.
  - Each dataset has recorded `n_instances / n_features / n_classes / minority_fraction / task_type`
    (the catalog + `infer_metadata` already compute these on import).
  - The suite is actually **run** under a multi-fold constraint (`1h`/`4h`) so Phases 1–2 have real
    mean±std + significance data.
- Non-functional:
  - Reuse the verified Kaggle refs (parent plan, phase-04) + the existing import pipeline; no new import
    code. Record the final suite (refs + tiers) in this phase file for reproducibility.

## Architecture

No new code — orchestration + data. Import via the console Datasets page / `ingest.kaggle_import` using
the live-verified refs (parent plan phase-04 table: adult_income, breast_cancer, telco_churn, abalone,
california_housing, wine_quality, wine, obesity, give_me_credit(mirror), house_prices(mirror),
forest_cover(mirror); `santander` unresolved). `infer_metadata` fills the tiers; `by_characteristics`
buckets them. Then launch AMLB (`runner.launch`) per framework under `1h`/`4h`. Local compute is the
constraint (some datasets are large, e.g. forest_cover 581k) — likely needs CI/a Linux box.

## Related Code Files

- Reference (no change): `storage/ingest.py` (`kaggle_import`), `console/views/datasets.py`,
  `analysis/by_characteristics.py`, `storage/runner.py` (`launch`).
- Modify (data/docs): record the final dataset suite (refs, task type, tiers, target column) in this
  phase file and/or a small catalog manifest; commit the resulting `results.csv` / DB snapshot.

## Implementation Steps

1. Choose the final ~12–20 datasets to evenly cover task type × size × dim × balance; write the list
   (ref + tier assignment) into this phase file.
2. Import each via the console Kaggle/upload path; verify `infer_metadata` populated the tiers
   (Datasets → Catalog overview should span all tiers, no `unknown`).
3. Handle `santander` (find a working mirror, manual download, or drop it and note why).
4. Run AMLB per framework under a multi-fold constraint (`1h`/`4h`); ingest results.
5. Sanity-check coverage in the console (by-characteristic view spans all tiers; enough complete blocks
   for Phase 1's Friedman/CD).

## Success Criteria

- [ ] Catalog spans **≥10 datasets** across all three task types and the size/dim/balance tiers, each
      with recorded characteristics (no `unknown`).
- [ ] The suite is run under a multi-fold constraint and ingested, giving Phases 1–2 real mean±std +
      significance data.
- [ ] The final suite (refs + tiers) is recorded for reproducibility.

## Risk Assessment

- **Risk:** local compute can't run large datasets × 4 frameworks × 10 folds. **Mitigation:** run on
  CI / a Linux box (the runner already targets Docker/Linux); or cap the largest datasets / fold count
  and log the reduction — never silently drop.
- **Risk:** `santander` (competition) has no dataset mirror. **Mitigation:** substitute another
  imbalanced binary dataset to keep the balance-tier coverage; record the swap.
- **Risk:** tier coverage skewed. **Mitigation:** assign tiers up front (step 1) and check the
  by-characteristic view actually spans them before running.
