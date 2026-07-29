---
phase: 3
title: "Bradley-Terry ranking-flip (Python approximation)"
status: pending
priority: P2
effort: "1.5-2d"
dependencies: [2]
---

# Phase 3: Bradley-Terry ranking-flip (Python approximation)

## Overview

The paper's most distinctive analytical method is the **Bradley-Terry tree**: it uses
pairwise win/loss comparisons between frameworks and recursively splits datasets by
characteristics (size, #features, missing-value ratio, class balance) to find where the
*relative ranking flips* with statistical significance. Build a **lightweight Python
approximation** that delivers the same insight — "on group X framework A wins, on group Y
framework B wins" — without an R dependency, and label it honestly as an approximation.

## Requirements

- Functional:
  - Compute **pairwise win rates** between frameworks from per-task scores (who beats whom, per dataset/fold).
  - For each candidate characteristic (`size_tier`, `dim_tier`, `balance_tier`, `task_type`),
    split datasets and detect where the **within-group ranking differs** from the global ranking (a "flip").
  - Rank characteristics by how strongly they change the ordering (e.g. Kendall-tau distance
    between global and per-group rankings, or fraction of framework pairs whose winner flips).
  - Render a **Ranking-flip** section: the global pairwise matrix + the top splitting
    characteristic with a before/after (global vs per-group) ranking comparison.
- Non-functional:
  - Pure logic in `analysis/ranking_flips.py`; FE renders only.
  - Honest labelling: section subtitle states this approximates the paper's Bradley-Terry
    trees (no significance test / recursive partitioning).
  - Uses the real characteristics from **Phase 2** (depends on it).

## Architecture

Method (KISS, no new heavy deps — pandas only):
1. **Pairwise wins:** for each dataset (and fold), compare each framework pair on `score`
   (higher = better; reuse `load_results.score`). Aggregate to a win-rate matrix `W[a,b]`.
2. **Global ranking:** order frameworks by overall win rate (consistent with `rankings.avg_rank`; cross-check).
3. **Per-group ranking:** using Phase-2 characteristics, recompute the win-rate ranking within each tier of a characteristic.
4. **Flip score per characteristic:** compare the per-group orderings against the global
   ordering (Kendall-tau distance averaged over groups, or count of pair-winner flips).
   The characteristic with the largest flip score is the "best split" — the analogue of the
   BT tree's first split.
5. Return: global matrix, per-characteristic flip scores, and the winning split's group rankings.

This mirrors the BT tree's *decision* ("which characteristic most changes the ranking") with
a transparent, testable statistic instead of model-based recursive partitioning. Optional:
a shallow 1-level split is enough for the thesis story; deeper trees are a non-goal.

## Related Code Files

- Create: `analysis/ranking_flips.py` — `win_matrix(df)`, `global_order(df)`,
  `group_orders(df, by)`, `flip_scores(df, chars=[...])`, `best_split(df)`, `main(argv)` CLI
  (mirror the other `analysis/*` module shape).
- Modify: `analysis/explorer.py` — add `ranking_flips_module()` via `_optional_module`.
- Modify: `console/views/evaluation.py` — add "Ranking-flip (Bradley-Terry approximation)"
  section: heatmap of the pairwise win matrix + a table/bar of the best split's per-group ranking, with the honesty caption.
- Create: `tests/test_ranking_flips.py` — synthetic df where a known characteristic flips the
  ranking (e.g. framework A wins on small, B wins on large) → assert `best_split` finds it.

## Implementation Steps

1. Implement `win_matrix` + `global_order` from per-task/fold `score`; cross-check global order against `rankings.average_ranks` on the same data.
2. Implement `group_orders` + `flip_scores` (Kendall-tau or pair-flip count) over the Phase-2 characteristics.
3. Implement `best_split` returning the top characteristic + its per-group rankings.
4. Add `ranking_flips_module()` to `explorer.py`.
5. Add the Evaluation section (Plotly heatmap + comparison table) guarded by graceful degrade; caption clearly says "approximation of Bradley-Terry trees (Strobl et al., 2011) — no significance test".
6. Write `tests/test_ranking_flips.py` with a constructed flip; run `pytest tests/test_ranking_flips.py -q`.

## Success Criteria

- [ ] `analysis/ranking_flips.py` computes the pairwise win matrix and identifies the characteristic that most changes the ranking, unit-tested on a synthetic flip.
- [ ] Evaluation page shows the win matrix + the best split's global-vs-group ranking comparison.
- [ ] Section is explicitly labelled an approximation of Bradley-Terry trees.
- [ ] Degrades gracefully when characteristics are missing (falls back to global ranking only).

## Risk Assessment

- **Risk:** overclaiming statistical rigor. **Mitigation:** explicit "approximation, no p-value" caption + cite the paper's BT method as the full version (non-goal).
- **Risk:** tiny smoke suite → unstable/empty splits. **Mitigation:** require a minimum group size; show "not enough data to split" instead of a spurious flip; note it stabilizes with the full 20-dataset suite.
- **Risk:** win-rate order disagreeing with `avg_rank` order confuses readers. **Mitigation:** cross-check in tests and reuse `rankings` where possible so the two views stay consistent (INV-2).
