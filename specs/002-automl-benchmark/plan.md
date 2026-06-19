# Implementation Plan: AutoML Framework Benchmark (AMLB-style)

**Branch**: `002-automl-benchmark` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-automl-benchmark/spec.md`

## Summary

Reproduce a correct, fair benchmark of three AutoML frameworks (H2O AutoML, FLAML, AutoGluon) plus two reference baselines on tabular OpenML tasks, following *AMLB: an AutoML Benchmark* (Gijsbers et al., JMLR 2024).

**Technical approach — reuse, don't rebuild:** use the official open-source `automlbenchmark` (AMLB) tool as the orchestration harness. It already enforces the identical protocol the whole project is about — fixed OpenML folds, equal time budgets, per-task metrics, controlled resources — and it captures/categorizes failures and emits a tidy results CSV. We add only (a) a thin **config layer** (which datasets / which budgets), (b) a small **analysis layer** (rankings, Pareto, by-characteristic), and (c) the **report**. Building a custom harness would be slower *and* re-introduce the exact pitfalls the thesis exists to avoid.

**MVP-first sequencing (fastest path to User Story 1):** a 3-dataset smoke run in AMLB **local mode** (short budget, 1 fold) to prove the pipeline end-to-end in ~1 day → then scale to ~12 datasets in **containerized mode** for the reproducible thesis numbers → then layer on failure/Pareto/by-characteristic analysis (mostly free from AMLB output) and the report.

## Technical Context

**Language/Version**: Python 3.11 for the AMLB tool and the analysis layer. AMLB provisions each framework's own environment, so framework version pins are isolated from ours.

**Primary Dependencies**: `automlbenchmark` (orchestration). Frameworks (all AMLB-integrated): `H2OAutoML`, `flaml`, `AutoGluon` (best-quality preset). Baselines (AMLB-integrated): `constantpredictor`, `RandomForest`, `TunedRandomForest`. Analysis: `pandas`, `matplotlib`/`seaborn`. Data: OpenML via AMLB's built-in loader.

**Storage**: Files only — AMLB results CSV(s) under `results/`, generated summary tables/plots, and config YAML in an AMLB user dir. No database.

**Testing**: The MVP smoke run *is* the end-to-end integration test (proves US1). `pytest` for the analysis layer (results parsing, ranking computation, coverage/failure tallies) against a small recorded fixture CSV.

**Target Platform**: Linux — a local GPU box and/or cloud; Docker for the final reproducible runs.

**Project Type**: Single project — a CLI-driven data-science benchmark + analysis. Not a service, library, or app.

**Performance Goals**: MVP smoke (3 datasets × 6 runners × 1 fold × ~10-min budget) finishes within a few hours → first ranking table the same day. Full suite (~12 datasets × 6 runners × 10 folds × 1 h) is large → run on GPU/cloud, parallelize across tasks, scale incrementally.

**Constraints**: Bounded time/compute; identical protocol per task (same folds, budget, metric, resources); no data leakage (AMLB's fixed OpenML folds); fully reproducible (fixed seeds, recorded versions, containerized final runs); GPU used for AutoGluon best-quality.

**Scale/Scope**: 3 frameworks + 2–3 baselines; ~10–15 datasets spanning binary / multiclass / regression and ≥3 dataset-size tiers; primary 1 h budget + optional 4 h budget.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

The active constitution (`.specify/memory/constitution.md`) is scoped to the **Med-VQA** project. Its cross-cutting principles apply to this feature; its medical-specific clauses do not (see Complexity Tracking).

| Principle | Status | Note |
|---|---|---|
| I. Medical safety & mandatory citations (NON-NEGOTIABLE) | N/A — justified | No clinical decision-making. If a medical dataset (e.g., disease prediction) is included, it is only a benchmark scoring target, never diagnostic output. No patient/PHI data is used. |
| II. Reproducibility (NON-NEGOTIABLE) | PASS — central to the feature | AMLB fixes seeds and records framework/dataset versions and run config; final runs are containerized; a one-command re-run regenerates the tables/plots. |
| III. Data integrity & no leakage (NON-NEGOTIABLE) | PASS | AMLB uses fixed OpenML train/test folds, identical across frameworks; test/validation data never trains or selects models. |
| IV. Evaluation gate / report vs. baseline | PASS | Constant-predictor and tuned-random-forest baselines; every framework is reported against both, per task. |
| V. Simplicity / YAGNI | PASS | Reuse AMLB rather than a custom harness; local mode before Docker; 3-dataset MVP before scaling. Any added complexity must be measurably justified here. |

**Post-Phase-1 re-check**: unchanged — the design adds only a thin config layer and an analysis layer; no new architectural complexity is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/002-automl-benchmark/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── results-schema.md
│   ├── benchmark-config-schema.md
│   └── analysis-outputs.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
automl-benchmark/                # self-contained thesis project, isolated from the host backend
├── README.md
├── requirements.txt             # amlb + analysis deps (pandas, matplotlib/seaborn, pytest)
├── amlb_userdir/                # passed to AMLB via -u / --userdir
│   ├── benchmarks/
│   │   ├── mvp.yaml             # 3 small datasets (smoke test) — US1 MVP
│   │   └── thesis.yaml         # ~12 datasets across 3 task types and 3 size tiers
│   ├── constraints.yaml         # budgets: smoke (~10m,1fold), 1h (10fold), 4h (optional)
│   └── frameworks.yaml          # framework/preset overrides if needed
├── scripts/
│   ├── run_mvp.sh              # loops frameworks+baselines, local mode, smoke budget
│   └── run_full.sh             # docker mode, full suite, 1h(+4h) budget
├── analysis/
│   ├── load_results.py         # parse AMLB results CSV → tidy dataframe
│   ├── rankings.py             # per-task rank → average rank, per task type
│   ├── coverage.py             # success rate + failures by category, per framework
│   ├── pareto.py               # accuracy vs inference time → Pareto frontier
│   └── by_characteristics.py   # group rankings by size / dimensionality / class balance
├── results/                     # AMLB output CSVs + generated tables/plots
└── report/
    └── report.md               # thesis writeup; cites AMLB; "pitfalls avoided" section
```

**Structure Decision**: A single self-contained project directory `automl-benchmark/` at the repo root. It holds an AMLB **user dir** (custom benchmark/constraint configs), thin run scripts, an analysis package, results, and the report. The AMLB tool itself is installed as an external dependency (cloned or pip), **not vendored**. This isolates the thesis project from the host SkillHub backend while living alongside the existing `specs/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Constitution stack deviation — this feature uses the AutoML/OpenML ecosystem, not the constitution's Med-VQA stack (PyTorch/HF, medical datasets/licenses) | The active constitution is scoped to a *different* feature (Med-VQA); this benchmark is a distinct project sharing the same spec-kit workspace | Forcing the Med-VQA stack and medical clauses onto an AutoML benchmark is nonsensical. Recommendation: scope the medical-specific clauses to the Med-VQA feature, or author a feature-specific constitution for `002-automl-benchmark`. Cross-cutting principles II–V are honored unchanged. |
