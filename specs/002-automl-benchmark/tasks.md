---
description: "Task list for AutoML Framework Benchmark (AMLB-style)"
---

# Tasks: AutoML Framework Benchmark (AMLB-style)

**Input**: Design documents from `/specs/002-automl-benchmark/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Analysis-layer unit tests ARE included — `plan.md` (Technical Context → Testing) specifies `pytest` for the analysis layer because incorrect rankings/coverage would invalidate the thesis. No TDD ceremony beyond that; the AMLB tool itself is the (externally) tested harness, and the smoke run is the end-to-end integration check.

**Organization**: Tasks are grouped by user story (US1–US7 from spec.md) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US7 (user-story phases only)

## Path Conventions

Single self-contained project rooted at the **repo root** (the `automl-thesis` repo itself — no nested `automl-benchmark/` dir; per plan.md Structure Decision). The AMLB tool is installed as an external dependency, not vendored; US7-generated framework modules live under `amlb_userdir/extensions/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton + working AMLB install.

- [X] T001 Create the project structure at the repo root (`amlb_userdir/benchmarks/`, `scripts/`, `analysis/`, `results/`, `report/`, `tests/fixtures/`) per plan.md Project Structure
- [X] T002 Install the AMLB tool and create `requirements.txt` (automlbenchmark deps + `pandas`, `matplotlib`, `seaborn`, `pytest`); document install + run commands in `README.md`
- [X] T003 [P] Smoke-verify the AMLB install by running its built-in short `test` benchmark for one framework; record the exact command in `README.md`
- [X] T004 [P] Verify GPU/CUDA availability for AutoGluon (`nvidia-smi`) and note the result + CPU fallback in `README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The config + results-parsing plumbing every story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `amlb_userdir/constraints.yaml` defining `smoke` (folds 1, 600s), `1h` (folds 10, 3600s), `4h` (folds 10, 14400s) with fixed cores/memory, per [contracts/benchmark-config-schema.md](./contracts/benchmark-config-schema.md)
- [X] T006 [P] Create `amlb_userdir/benchmarks/mvp.yaml` with the MVP-3 tasks: `credit-g` (168757), `vehicle` (190146), `Moneyball` (167210)
- [X] T007 [P] Create `amlb_userdir/frameworks.yaml` pinning the AutoGluon best-quality (GPU) preset and any runner/baseline overrides, per research.md D6/D7
- [X] T008 Implement `analysis/load_results.py` to parse an AMLB results CSV into a tidy dataframe (normalize metric direction; flag success vs failure) per [contracts/results-schema.md](./contracts/results-schema.md)
- [X] T009 [P] Add `tests/fixtures/results_sample.csv` (small AMLB-shaped CSV with successes + seeded failures) and `tests/test_load_results.py`

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 - Fair head-to-head comparison under one identical protocol (Priority: P1) 🎯 MVP

**Goal**: Run the 3 frameworks + baselines on the MVP-3 datasets under one identical protocol and produce per-task scores + an overall average-rank table.

**Independent Test**: Per [quickstart.md](./quickstart.md) Steps 1–2 — run all runners on MVP-3, then confirm from the CSV that every runner on a task shared the same metric/folds/budget, and that the ranking table renders.

- [X] T010 [US1] Create `scripts/run_mvp.sh` looping runners `H2OAutoML flaml AutoGluon constantpredictor RandomForest TunedRandomForest` over benchmark `mvp` + constraint `smoke`, local mode, `-u amlb_userdir`, writing to `results/`
- [X] T011 [US1] Execute `scripts/run_mvp.sh` to produce the MVP results CSV in `results/` (all 6 runners × MVP-3 × 1 fold) — depends on T005, T006, T010
- [X] T012 [P] [US1] Implement `analysis/rankings.py` (per-task rank within task type → average rank; never mix metrics across types) reading via `load_results` (FR-008) — depends on T008
- [X] T013 [P] [US1] Add `tests/test_rankings.py` verifying rank direction per metric (auc higher-better; logloss/rmse lower-better) on the fixture
- [X] T014 [US1] Run `rankings.py` on the MVP CSV to emit the per-task score table + overall average-rank table to `results/` — depends on T011, T012
- [X] T015 [US1] Validate US1 in `report/report.md` (preliminary): confirm from the CSV that every runner on each task shares the same metric, fold count, and budget (SC-002), and that the ranking table renders

**Checkpoint**: MVP complete — a defensible fair comparison on 3 datasets.

---

## Phase 4: User Story 2 - Failures captured and coverage reported (Priority: P2)

**Goal**: Categorize failures (memory/time/data/implementation) and report per-runner coverage; failures are never silently dropped.

**Independent Test**: A failure-prone run (large task under a tight budget) is recorded with a category and appears in the coverage table, not absent.

- [ ] T016 [P] [US2] Implement `analysis/coverage.py` — per-runner success rate, failures grouped into memory/time/data/implementation (D9 mapping), and budget-adherence from `training_duration` (FR-006, FR-015) — depends on T008
- [ ] T017 [P] [US2] Add `tests/test_coverage.py` verifying the failure-category mapping + coverage math on the fixture
- [ ] T018 [US2] Run `coverage.py` on the available results CSV to emit the coverage table to `results/` — depends on T016
- [ ] T019 [US2] Validate US2: ensure at least one failure-prone run exists (a large task under a tight budget, surfacing in the scaled run T028) and confirm it is categorized and counted, never dropped (SC-001)

**Checkpoint**: Robustness is reported alongside accuracy.

---

## Phase 5: User Story 3 - Accuracy vs. inference-time trade-off (Priority: P2)

**Goal**: Present the accuracy-versus-inference-time trade-off and identify Pareto-optimal frameworks.

**Independent Test**: Each model has a recorded (score, inference-time) pair; the Pareto plot marks optimal frameworks.

- [X] T020 [P] [US3] Implement `analysis/pareto.py` — per-runner median score vs median `predict_duration`; flag Pareto-optimal (FR-009) — depends on T008
- [X] T021 [P] [US3] Add `tests/test_pareto.py` verifying Pareto-frontier selection on the fixture
- [X] T022 [US3] Run `pareto.py` to emit the accuracy-vs-inference-time table + plot to `results/` — depends on T020

**Checkpoint**: The accuracy/speed trade-off is quantified.

---

## Phase 6: User Story 4 - How rankings shift with data characteristics (Priority: P3)

**Goal**: Show how the relative ranking changes with dataset size, dimensionality, and class balance.

**Independent Test**: Grouped by a characteristic (e.g., small vs. large), the per-group rankings are produced and differences reported.

- [ ] T023 [US4] Create `amlb_userdir/benchmarks/thesis.yaml` (~12 tasks across 3 task types × 3 size tiers, including `churn` 359968) per research.md D3
- [X] T024 [P] [US4] Implement `analysis/by_characteristics.py` — derive size/dim/balance tiers from task metadata (n, p, class_ratio) and group rankings (FR-010) — depends on T008
- [X] T025 [P] [US4] Add `tests/test_by_characteristics.py` verifying tier bucketing + grouped ranking on the fixture
- [X] T026 [US4] Run `by_characteristics.py` to emit grouped ranking tables/plots to `results/` — depends on T024 (and full-suite data from T028 for meaningful spread)

**Checkpoint**: Strengths/weaknesses by data regime are visible.

---

## Phase 7: User Story 5 - One-command reproducibility and thesis report (Priority: P3)

**Goal**: A documented command re-runs the benchmark and regenerates all tables/plots; the report ties findings to the AMLB paper and lists pitfalls avoided.

**Independent Test**: From a clean environment, the documented command regenerates the headline tables/plots; the report cites AMLB and has a "pitfalls avoided" section.

- [ ] T027 [US5] Create `scripts/run_full.sh` looping all runners over benchmark `thesis` + constraint `1h`, docker mode, `-u amlb_userdir`, output to `results/` — depends on T005, T007, T023
- [ ] T028 [US5] Execute `scripts/run_full.sh` to produce the full thesis results CSV (the long GPU/cloud run) — depends on T027
- [ ] T029 [US5] Re-run rankings/coverage/pareto/by_characteristics on the full CSV to regenerate all final tables/plots into `results/` — depends on T028, T012, T016, T020, T024
- [ ] T030 [US5] Write the reproducibility section in `README.md`: the single documented command + version-controlled `amlb_userdir/` + Docker images regenerate the headline results (FR-011, SC-004)
- [ ] T031 [US5] Write `report/report.md`: findings (best overall, ranking shifts, accuracy/inference trade-off), cite AMLB, and a "pitfalls avoided" section covering unequal budgets / inconsistent metrics / ignored failures / no isolation (FR-012, SC-005, SC-006) — depends on T029

**Checkpoint**: Thesis-grade, reproducible deliverable.

---

## Phase 8: User Story 6 - Interactive dashboard to explore the results (Priority: P3)

**Purpose**: Turn the recorded results into a navigable interactive view (reuses the analysis modules; reads recorded data only).

> **Consolidation note (post-delivery)**: T036–T039 were first delivered as a standalone `dashboard/app.py`.
> It was later consolidated into the **console Evaluation page** (`console/views/evaluation.py`), and the
> UI-free pure layer moved to **`analysis/explorer.py`** (unit-tested in `tests/test_explorer.py`). The
> contract (INV-1/INV-2, the three views, filters, export) is unchanged — only the host moved.

- [X] T036 [US6] Add `streamlit` + `plotly` to `requirements.txt` and create `dashboard/app.py` skeleton — a Streamlit app that takes `--results <csv>`, loads it via `analysis/load_results.py`, and lays out the sidebar filters (framework / task type / dataset / budget) per [contracts/dashboard-contract.md](./contracts/dashboard-contract.md) — depends on T008
- [X] T037 [US6] Wire the three views in `dashboard/app.py` by reusing `rankings.py` / `pareto.py` / `by_characteristics.py` (no recomputation; INV-2) and binding the sidebar filters so every filter change re-derives all views (FR-016) — depends on T036, T012, T020, T024
- [X] T038 [P] [US6] Add a "headline figures" static export (matplotlib/seaborn) from the same recorded data for inclusion in the report (FR-016)
- [X] T039 [US6] Validate US6: launch the dashboard on an existing results CSV, confirm the three views render, filtering updates them, malformed/empty CSV shows an empty-state (not a crash), and **no benchmark run is triggered** (INV-1, SC-008)

**Checkpoint**: Recorded results are explorable interactively; headline figures exportable.

---

## Phase 9: User Story 7 - One skill to integrate a new framework into the harness (Priority: P3, developer tooling)

**Purpose**: A reusable Claude Code skill that scaffolds + verifies a harness framework module from a conforming source framework. Independent of FR-001 (does not change frameworks under test).

- [ ] T040 [US7] Create the scaffold templates under `.claude/skills/amlb-integrate-framework/templates/` — parameterized `__init__.py`, `exec.py`, `setup.sh`, `requirements.txt`, and a `frameworks.yaml` entry stub (`module: extensions.<Name>`). The skill emits the rendered module into `amlb_userdir/extensions/<Name>/` and appends the entry to `amlb_userdir/frameworks.yaml` (AMLB's canonical userdir pattern; external clone untouched), matching the emitted-artifacts section of [contracts/framework-integration-contract.md](./contracts/framework-integration-contract.md)
- [ ] T041 [US7] Author `.claude/skills/amlb-integrate-framework/SKILL.md` — the workflow + the enforced preconditions P1–P4 (Python / pip-installable / exposes fit-predict / unique name) and the adapter obligations (predictions only; harness scores), per [contracts/framework-integration-contract.md](./contracts/framework-integration-contract.md) (FR-017) — depends on T040
- [ ] T042 [P] [US7] Encode precondition enforcement in `SKILL.md`: a non-conforming source (no installable package / no fit-predict surface / name collision) is rejected with the stated failing rule and **no partial module** is written (US7 acceptance #2, SC-009)
- [ ] T043 [US7] Define the verification step in `SKILL.md`: the generated module runs `runbenchmark.py <Name> mvp smoke -m local -u amlb_userdir` and yields scored predictions, with the module producing predictions only while the harness scores (FR-017, FR-003/FR-014) — depends on T041
- [ ] T044 [US7] Validate US7 end-to-end on one example Python fit/predict framework: scaffold → smoke run → scored predictions; document usage in the skill's `SKILL.md`/README (SC-009) — depends on T041, T042, T043

**Checkpoint**: A new conforming framework can be integrated and smoke-verified via one skill.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Optional: execute a `4h`-budget run on a subset and add a budget-effect comparison (FR-004) to `report/report.md`
- [ ] T033 [P] Optional: explore AMLB's bundled interactive visualization to cross-check the scripted figures
- [ ] T034 Run the full `quickstart.md` validation end-to-end in a clean environment and fix any gaps
- [ ] T035 [P] Finalize `README.md` (overview, install, run, repro) and clean up `results/` (keep summaries, gitignore raw artifacts)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup — BLOCKS all stories. `T008 load_results` blocks every analysis task.
- **US1 (Phase 3)**: after Foundational — the MVP.
- **US2 / US3 / US4 (Phases 4–6)**: analysis impls depend only on `T008`; independently implementable/testable on fixtures + the smoke CSV. Their *final* figures use the full-suite CSV from `T028`.
- **US5 (Phase 7)**: depends on US1–US4 (runs the full benchmark and uses all analyses to produce the report).
- **US6 (Phase 8)**: depends on the analysis impls it reuses (`T012`, `T020`, `T024`) and `T008`; read-only over recorded data, so it needs *some* results CSV but never a new run. Independently testable on the smoke CSV.
- **US7 (Phase 9)**: depends only on the existing AMLB framework contract (mirrors `frameworks/flaml/`); independent of FR-001 and of US1–US6. Its smoke verification reuses the `mvp`/`smoke` config (`T006`, `T005`).
- **Polish (Phase 10)**: after the desired stories.

### Critical path to MVP

`T001 → T002 → T005 → T006 → T010 → T011` (run) and `T008 → T012` (rankings) → `T014 → T015`.

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T006, T007, T009 in parallel (different files) after T005/T008 scaffolding.
- Analysis impls across stories — T012, T016, T020, T024 — are different files and all depend only on T008, so they can be built in parallel once Foundational is done.
- Each analysis impl pairs with its [P] unit test (T013, T017, T021, T025).
- US6 static export (T038) is [P] alongside the view-wiring; US7 precondition encoding (T042) is [P] alongside the SKILL.md verification step.
- **US6 and US7 are mutually independent** and can be built in parallel by two people once the analyses (for US6) exist; US7 needs nothing from US1–US6.

---

## Parallel Example: analysis layer (after T008)

```bash
Task: "Implement analysis/rankings.py"          # T012 [US1]
Task: "Implement analysis/coverage.py"          # T016 [US2]
Task: "Implement analysis/pareto.py"            # T020 [US3]
Task: "Implement analysis/by_characteristics.py"# T024 [US4]
```

---

## Implementation Strategy

### MVP First (User Story 1 only) — fastest path

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1.
4. **STOP and VALIDATE**: the smoke run + ranking table = a defensible fair comparison on 3 datasets (T015).
5. Demo the MVP.

The only real time cost in the MVP is the smoke run (T011, ~minutes-to-hours on small data). Everything else is config + a small parser + a ranking function.

### Incremental Delivery

MVP (US1, smoke) → add coverage (US2) → add Pareto (US3) → add thesis suite + by-characteristic (US4) → scale to the full reproducible run + report (US5). Each step adds value without breaking the previous.

**Optional P3 add-ons (any time after the analyses exist, in parallel):** US6 (interactive dashboard over the recorded CSV) and US7 (the framework-integration skill). Neither blocks the thesis deliverable: US6 makes existing results explorable; US7 is reusable developer tooling and does not touch the three-frameworks-under-test comparison (FR-001).

---

## Notes

- [P] = different files, no incomplete dependencies.
- The expensive long run is T028 (full suite, 1 h × 10 folds, Docker); keep it for US5 after the analyses are proven on the smoke CSV.
- Commit after each task or logical group; keep work on a feature branch (do not commit to `dev`).
- US2's real failures appear at scale (T028); its logic is unit-tested earlier on the fixture (T017).
