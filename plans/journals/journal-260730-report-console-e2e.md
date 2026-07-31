# Report and Console Finally Agree (Option C, 6/6 Phases)

**Date**: 2026-07-30 23:08
**Severity**: Medium
**Component**: `analysis/*`, `console/views/evaluation.py`, `console/views/datasets.py`, `storage/ingest.py`
**Status**: Resolved

## What Happened

Started this plan meaning to "merge figures into `report_v2.md`" — a doc-tidying task. Digging
in, it turned out the report's real pipeline (`scripts/run_automl.py` → `reports/run_*.json` →
`notebooks/analysis.ipynb`) lived on `origin/main` and had never been wired into the AMLB
console. The console's live data was a 3-dataset `smoke` run with different frameworks
entirely. That's a direct violation of this repo's own stated invariant, INV-2 in
`analysis/explorer.py`: "the Evaluation page and the report can never disagree." They
disagreed completely — different datasets, different frameworks, different everything.

## The Brutal Truth

The scope-defining moment here wasn't a bug, it was realizing the deliverable I was asked to
polish (the report) was built from data the tool I was supposed to be improving (the console)
had never seen. Nobody had noticed because the report was static Markdown + PNGs — nothing
ever re-ran it against the console to check. That's the uncomfortable part: a stated invariant
in the codebase (INV-2) had silently been false the whole time, and no test caught it because
there was no test that could — the "report" wasn't code.

## Technical Details

Rejected two alternatives before landing on Option C ("bridge the report pipeline into the
console"): rebuild the whole analysis in Streamlit from scratch (redundant, ignores existing
`analysis/*` pattern), and leave the report static (perpetuates the INV-2 violation). Chosen
path: ingest `reports/*.json` into the `runs` table (`storage/ingest.ingest_report_json/_bytes`,
`repo.load()` gained additive `info`/`metrics` JSON columns — no migration) and add six new
pure `analysis/*` modules discovered via `explorer._optional_module` with graceful degrade:
`by_characteristics.load_task_meta`, `ranking_flips.py` (Bradley-Terry approximation),
`score_shapes.py`, `memory.py`, `failures.by_size`.

Code review caught two real correctness bugs before they shipped:
- **Phase 3**: `ranking_flips`'s "global order" originally used raw pairwise win-rate, which
  could contradict the leaderboard's `average_ranks` under unequal framework participation —
  literally reintroducing INV-2 inside the new feature meant to demonstrate it. Fixed by
  reusing `rankings.average_ranks` as the shared ordering source.
- **Phase 5**: NULL `task_type` was silently dropped from 2 of 3 score-shape helpers
  (`normalized_scores`, `score_vs_time`) but kept in the third — cross-figure inconsistency.
  Fixed with a consistent `fillna("unknown")` across all three.

## What We Tried / Root Cause

Root cause of the whole detour: the report's full 12-dataset × 2-budget × 4-framework
experiment was never committed anywhere — only a small 4-dataset, budget-30 run plus the
already-rendered figures survived. The Kaggle-import client (spec 006) resolves 11/12 dataset
references live; `santander` stays unresolved because it's a Kaggle *competition*, and our
client is datasets-only (documented as a non-goal, not a bug).

## Lessons Learned

An invariant stated in code comments (INV-2) is worthless if nothing exercises the path that
could violate it — a static report next to a live console is exactly that gap. When a "docs
polish" task starts revealing that generated artifacts don't trace back to any reproducible
pipeline in the repo, stop and re-scope; that's a data-provenance bug wearing a documentation
costume.

## Next Steps

Console now reproduces ~10/11 report figures E2E from `repo.load()`; only Hình 3
(target-distribution) stays a validated non-goal (needs raw-file plotting). Full suite: 117
passing. Backlog item recorded in `plan.md`: HTML report export (owner: next session, no
date set) — render leaderboard/Pareto/characteristic/failure/score figures into one
self-contained HTML mirroring `report_v2.md`, reusing `fig.to_html`.
