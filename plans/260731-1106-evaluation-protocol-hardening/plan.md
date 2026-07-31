---
title: "Evaluation-protocol hardening (AMLB Path B)"
description: "Adapt the benchmark to the paper's evaluation-rigor checklist on the AMLB console runner (Path B): statistical significance, k-fold mean±std, explicit budget/resource fairness, reproducible versions, and a broader dataset suite."
status: pending
priority: P1
effort: "5-8d"
tags: [analysis, evaluation, benchmark, statistics, reproducibility, thesis]
created: 2026-07-31
---

# Evaluation-protocol hardening (AMLB Path B)

## Overview

Harden the AutoML benchmark against the paper's evaluation-rigor checklist. Gap analysis
(2026-07-31) mapped the 17 criteria against the code and produced the backlog this plan executes
(see the parent plan's Backlog: `plans/260729-2133-amlb-multi-faceted-fe-failure-analysis-and-bradley-terry/plan.md`).

**Decision (with user):** the in-process `scripts/run_automl.py` (single-split, sklearn, 3
frameworks) is **frozen** — it only backs the *current* `report_v2.md`. The **AMLB console runner**
(`storage/runner.py`, Docker-per-framework, constraint-driven k-fold) is the **final code**; every
phase here targets it and the console/analysis layer around it.

### Already satisfied by the AMLB path — NO work in this plan
Per-framework **Docker isolation**; **default presets** (no hand-tune); **failure capture +
categorization + coverage%** (`analysis/failures.py`); **cross-task score normalization**
(`load_results.score` / `score_shapes.normalized_scores`); **separate inference time**
(`predict_duration` → Pareto); **constant / RandomForest baselines** (`migrate.BASELINES`);
**k-fold capability itself** — `constraints` already carries `folds` (seed: `smoke`=1, `1h`/`4h`=**10
folds**), and AMLB runs stratified CV internally, emitting per-fold rows into `runs`.

### What this plan closes (checklist §1/§3/§5/§6 + scope §2)

| Checklist gap | Phase |
|---|---|
| §5 Friedman + Nemenyi → critical-difference diagram; CI/±std on charts | **Phase 1** (highest value, standalone) |
| §1 k-fold CV surfaced as **mean ± std** + explicit split/fold config | **Phase 2** |
| §3 Explicit, provable **budget + CPU/RAM** fairness (allocated vs actual) | **Phase 3** |
| §6 Pin & **record framework versions**; one-command reproduce + fixed seed | **Phase 4** |
| §2 Expand suite to **~10–20 datasets** across task-type × size/dim/balance tiers | **Phase 5** |

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Significance testing (Friedman + Nemenyi CD diagram) + confidence on charts | P1 |
| 2 | Report k-fold **mean ± std**; make fold/split config explicit on Training | P2 |
| 3 | Explicit, logged budget + resource allocation so fairness is provable | P2 |
| 4 | Record framework versions; a single reproduce command with a fixed seed | P3 |
| 5 | Broaden the dataset suite to span all tiers, with recorded metadata | P3 |

## Phases

| # | Phase | Status | Priority | Depends |
|---|-------|--------|----------|---------|
| 1 | [Statistical significance + confidence](./phase-01-start.md) | Done | P1 | — |
| 2 | [k-fold CV mean±std + split config](./phase-02-k-fold-cv-mean-and-std-display.md) | Done | P2 | — |
| 3 | [Training budget & resource fairness](./phase-03-training-budget-and-resource-fairness.md) | Done | P2 | — |
| 4 | [Reproducibility: versions + one-command](./phase-04-reproducibility-version-pinning-and-one-command-rerun.md) | Done | P3 | — |
| 5 | [Expand dataset suite across tiers](./phase-05-expand-dataset-suite-across-tiers.md) | Pending | P3 | — |

Recommended order: **1 → 2 → 3 → 4 → 5**. Phase 1 is standalone and highest-value; Phases 2–4 are
mostly independent; Phase 5 is a data-collection task that enriches 1/2 (more datasets = stronger
Friedman/CD) and can run in parallel at any time. Phases 1–3 are most credible once Phase 5 (or any
multi-dataset, multi-fold run under the `1h`/`4h` constraint) has produced real data.

## Success Criteria

- [ ] Evaluation shows a **Friedman test verdict** + **Nemenyi critical-difference diagram**; charts
      carry ±std / CI, not bare means. All new stats live in a pure, tested `analysis/*` module.
- [ ] Per-(dataset×framework) results display **mean ± std over K folds**; Training makes the fold
      count / split protocol explicit; stratification is documented.
- [ ] Training surfaces the **allocated** budget + cores + memory, and the run records **actual**
      resource use, so equal-footing can be shown; degrades cleanly when a field is absent.
- [ ] Every `runs` row + any export carries the **framework version**; a documented single command
      reproduces a run with a fixed seed.
- [ ] The dataset catalog spans **≥10 datasets** across the three task types and the size/dim/balance
      tiers, each with recorded `n_instances / n_features / minority_fraction`.
- [ ] Analysis stays pure/UI-free (INV-1), reuses `repo.load()` (INV-2), and every view degrades
      gracefully (info message) when data/columns are missing.

## Non-Goals

- Changing or re-running `scripts/run_automl.py` (Path A is frozen for the current report).
- Re-implementing CV/isolation/baselines — AMLB already provides them; this plan surfaces & analyzes.
- A full anytime-performance study (the paper's own stated limitation).
- Competition-capable Kaggle client / `santander_satisfaction` (still unresolved; use dataset mirrors).

<!-- slug: evaluation-protocol-hardening -->
