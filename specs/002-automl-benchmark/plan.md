# Implementation Plan: AutoML Framework Benchmark (AMLB-style)

**Branch**: `002-automl-benchmark` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-automl-benchmark/spec.md`

## Summary

Reproduce a correct, fair benchmark of three AutoML frameworks (H2O AutoML, FLAML, AutoGluon) plus two reference baselines on tabular OpenML tasks, following *AMLB: an AutoML Benchmark* (Gijsbers et al., JMLR 2024).

**Technical approach — reuse, don't rebuild:** use the official open-source `automlbenchmark` (AMLB) tool as the orchestration harness. It already enforces the identical protocol the whole project is about — fixed OpenML folds, equal time budgets, per-task metrics, controlled resources — and it captures/categorizes failures and emits a tidy results CSV. We add only (a) a thin **config layer** (which datasets / which budgets), (b) a small **analysis layer** (rankings, Pareto, by-characteristic), and (c) the **report**. Building a custom harness would be slower *and* re-introduce the exact pitfalls the thesis exists to avoid.

**MVP-first sequencing (fastest path to User Story 1):** a 3-dataset smoke run in AMLB **local mode** (short budget, 1 fold) to prove the pipeline end-to-end in ~1 day → then scale to ~12 datasets in **containerized mode** for the reproducible thesis numbers → then layer on failure/Pareto/by-characteristic analysis (mostly free from AMLB output) and the report.

**Two P3 add-ons (post-MVP), both reuse — not rebuild:** (US6) an **interactive dashboard** that reads the recorded results CSV and re-renders the existing analysis (ranking / Pareto / by-characteristic) with filters — pure presentation over data US1–US4 already produce, **no new runs**; (US7) a **Claude Code skill** that scaffolds + smoke-verifies a new AMLB framework module from a conforming source framework — reusable developer tooling that does **not** change the three frameworks under test (FR-001).

## Technical Context

**Language/Version**: Python 3.9 — matching the AMLB tool's pinned interpreter (`resources/config.yaml versions.python: 3.9`; framework venvs are Python 3.9 too) for the analysis/dashboard layer to avoid drift. AMLB provisions each framework's own environment, so framework version pins are isolated from ours.

**Primary Dependencies**: `automlbenchmark` (orchestration). Frameworks (all AMLB-integrated): `H2OAutoML`, `flaml`, `AutoGluon` (best-quality preset). Baselines (AMLB-integrated): `constantpredictor`, `RandomForest`, `TunedRandomForest`. Analysis: `pandas`, `matplotlib`/`seaborn`. Data: OpenML via AMLB's built-in loader. **Dashboard (US6)**: `streamlit` + `plotly` (interactive views over the results CSV). **Integration skill (US7)**: a Claude Code skill (Markdown `SKILL.md` + scaffold templates) — no new runtime dependency; the generated module reuses AMLB's framework contract.

**Resolved clarifications (was NEEDS CLARIFICATION)**: (1) **Dashboard stack = Streamlit + Plotly** — chosen for the lowest-friction pure-Python interactive app that reuses `analysis/*` and `load_results.py` with no callback boilerplate; `matplotlib`/`seaborn` remain for static report-figure export (see research D11). (2) **Integration tooling = a Claude Code skill** taking a Python, pip-installable framework exposing `fit`/`predict`, emitting an `amlb_userdir/extensions/<Name>/` module + `frameworks.yaml` entry (`module: extensions.<Name>`), verified on the `smoke` suite (see research D12).

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

**Post-Phase-1 re-check**: still PASS. The two P3 add-ons preserve every gate: US6 is read-only presentation over recorded data (no new runs, no leakage surface), and US7 *wraps* a framework into the existing AMLB contract (produces predictions only; the harness still scores — FR-003/FR-014 intact, baselines unaffected). Principle V (simplicity) is honored by choosing Streamlit (no callback boilerplate) and a Markdown skill over a bespoke generator. No new architectural complexity is introduced.

> Constitution file status (2026-06-22): `.specify/memory/constitution.md` is currently the un-ratified template (reset during the spec-kit bootstrap in this workspace). The cross-cutting principles II–V are therefore applied here as documented design discipline rather than read from a ratified file. Recommend running `/speckit-constitution` to ratify a feature-scoped constitution before the final report; this is not a blocker for planning.

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
<repo root>                       # the automl-thesis repo IS the self-contained project
├── README.md
├── requirements.txt             # amlb + analysis deps (pandas, matplotlib/seaborn, pytest)
├── amlb_userdir/                # passed to AMLB via -u / --userdir
│   ├── benchmarks/
│   │   ├── mvp.yaml             # 3 small datasets (smoke test) — US1 MVP
│   │   └── thesis.yaml         # ~12 datasets across 3 task types and 3 size tiers
│   ├── constraints.yaml         # budgets: smoke (~10m,1fold), 1h (10fold), 4h (optional)
│   ├── frameworks.yaml          # framework/preset overrides + custom (module: extensions.<Name>)
│   └── extensions/              # US7 — generated custom framework modules land here
│       └── <Name>/             #   __init__.py / exec.py / setup.sh / requirements.txt
├── scripts/
│   ├── run_mvp.sh              # loops frameworks+baselines, local mode, smoke budget
│   └── run_full.sh             # docker mode, full suite, 1h(+4h) budget
├── analysis/
│   ├── load_results.py         # parse AMLB results CSV → tidy dataframe
│   ├── rankings.py             # per-task rank → average rank, per task type
│   ├── coverage.py             # success rate + failures by category, per framework
│   ├── pareto.py               # accuracy vs inference time → Pareto frontier
│   └── by_characteristics.py   # group rankings by size / dimensionality / class balance
│   └── explorer.py             # US6 explorer engine — UI-free pure layer (filters, ranking tables,
│                               #   optional-module discovery, headline export); reused by the console
├── console/                     # product console (spec 003); Evaluation page = US6 explorer UI (plotly)
├── results/                     # AMLB output CSVs + generated tables/plots
└── report/
    └── report.md               # thesis writeup; cites AMLB; "pitfalls avoided" section

.claude/skills/                  # US7 — repo-local developer tooling (the skill itself)
└── amlb-integrate-framework/    # Claude Code skill: scaffold + smoke-verify a new framework module
    ├── SKILL.md                # rules, preconditions (Python/pip/fit-predict), workflow
    └── templates/              # __init__.py / exec.py / setup.sh / requirements.txt / frameworks.yaml stubs
```

**Structure Decision**: The **repo root** (the `automl-thesis` repository itself) is the single self-contained project — there is no nested `automl-benchmark/` directory; `amlb_userdir/`, `scripts/`, `analysis/`, `results/`, `report/` live directly at the root. It holds an AMLB **user dir** (custom benchmark/constraint configs, plus `extensions/` for US7-generated framework modules), thin run scripts, an analysis package, results, and the report. The AMLB tool itself is installed as an external dependency (the clone at `~/workspace/automlbenchmark`), **not vendored** — and custom frameworks go in `amlb_userdir/extensions/` so the external clone is never modified.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Constitution stack deviation — this feature uses the AutoML/OpenML ecosystem, not the constitution's Med-VQA stack (PyTorch/HF, medical datasets/licenses) | The active constitution is scoped to a *different* feature (Med-VQA); this benchmark is a distinct project sharing the same spec-kit workspace | Forcing the Med-VQA stack and medical clauses onto an AutoML benchmark is nonsensical. Recommendation: scope the medical-specific clauses to the Med-VQA feature, or author a feature-specific constitution for `002-automl-benchmark`. Cross-cutting principles II–V are honored unchanged. |
