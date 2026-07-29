---
title: "AMLB multi-faceted FE - failure analysis and Bradley-Terry"
description: "Fill the two novel AMLB analysis dimensions the console is missing: failure categorization and ranking-flip (Bradley-Terry) analysis."
status: pending
priority: P1
effort: "3-5d"
tags: [analysis, frontend, evaluation, thesis]
created: 2026-07-29
---

# AMLB multi-faceted FE — failure analysis and Bradley-Terry

## Overview

The console already covers 2 of the paper's 4 "multi-faceted analysis" dimensions
(accuracy ranking, accuracy-vs-inference-time Pareto). The two **novel** dimensions are
missing or crude: **failure analysis** (only a raw count today) and **Bradley-Terry
trees** (only a hardcoded 5-dataset tier grouping). This plan adds both, following the
existing single-source-of-truth pattern: pure functions in `analysis/*`, discovered by
`analysis/explorer.py`, rendered in `console/views/evaluation.py`, unit-tested.

Scope decided with user: build **both** gaps; Bradley-Terry as a **lightweight, honest
Python approximation** (no R/rpy2 dependency).

### Map: paper contribution ↔ current system

| Paper dimension | Current system | This plan |
|---|---|---|
| Accuracy ranking | `rankings.py` + Overall leaderboard | — done |
| Inference-time trade-off | `pareto.py` + "Accuracy vs inference time" | — done |
| **Failure analysis** (Memory/Time/Data/Implementation) | Raw `N failures` KPI only | **Phase 1** |
| **Bradley-Terry** (auto-find ranking-flip task subsets) | Hardcoded 5-dataset tiers | **Phase 2 → Phase 3** |

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Categorized failure-analysis view (by category, framework, budget) — a headline paper contribution | P1 |
| 2 | Dataset characteristics sourced from the real catalog (not 5 hardcoded tasks) so views scale to the 20-dataset suite | P1 |
| 3 | Ranking-flip / Bradley-Terry-style view that surfaces where framework rankings change by data characteristic | P2 |

## Phases

| # | Phase | Status | Priority | Depends |
|---|-------|--------|----------|---------|
| 1 | [Failure analysis view](./phase-01-start.md) | Done | P1 | — |
| 2 | [Real dataset characteristics from catalog](./phase-02-real-dataset-characteristics-from-catalog.md) | Pending | P1 | — |
| 3 | [Bradley-Terry ranking-flip (Python approx)](./phase-03-bradley-terry-ranking-flip-python-approximation.md) | Pending | P2 | 2 |

Recommended order: **1 → 2 → 3**. Phase 1 is independent and highest-ROI; Phase 2
unblocks Phase 3 (and fixes the existing by-characteristic view's scaling).

## Success Criteria

- [ ] Evaluation page shows a **Failure analysis** section: failures split into
      Memory / Time / Data / Implementation, broken down by framework and by budget.
- [ ] By-characteristic and ranking-flip views read `n_instances / n_features /
      minority_fraction / task_type` from the **dataset catalog**, covering all datasets
      in the results (no hardcoded task list).
- [ ] Evaluation page shows a **Ranking-flip** section that names the data
      characteristic and split-point where the framework ranking changes, labelled
      honestly as an approximation of the paper's Bradley-Terry trees.
- [ ] All new logic lives in pure `analysis/*` modules with pytest coverage; FE only renders.
- [ ] Views degrade gracefully (info message) when a module/column is absent — same pattern as US3/US4.

## Non-Goals

- Full statistical Bradley-Terry model-based recursive partitioning via R (`partykit`/`psychotree`). Explicitly out of scope per the lightweight decision.
- Anytime-performance capture (the paper lists this as its own limitation).
- New result columns or benchmark-runner changes — analysis reads existing AMLB output.

<!-- slug: amlb-multi-faceted-fe-failure-analysis-and-bradley-terry -->
