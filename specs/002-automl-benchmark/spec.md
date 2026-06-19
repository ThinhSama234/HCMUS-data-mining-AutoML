# Feature Specification: AutoML Framework Benchmark (AMLB-style)

**Feature Branch**: `002-automl-benchmark`

**Created**: 2026-06-18

**Status**: Draft

**Input**: User description: "Reproducible, fair benchmark comparing three open-source AutoML frameworks — H2O AutoML, FLAML, AutoGluon — on tabular supervised-learning tasks, applying the methodology and best practices from *AMLB: an AutoML Benchmark* (Gijsbers et al., JMLR 2024) to avoid common benchmarking pitfalls. Thesis-grade deliverable: reproducible experiment code, recorded results, analysis, and a written report citing the paper. Compute available: GPU/cloud."

## User Scenarios & Testing *(mandatory)*

The "user" here is the **student/researcher** running the comparison and the **thesis readers** who must trust the results. Each story is an independently demonstrable slice; US1 alone is a viable MVP (a defensible head-to-head comparison).

### User Story 1 - Fair head-to-head comparison under one identical protocol (Priority: P1)

The researcher runs all three frameworks (plus reference baselines) across the selected datasets under a single, identical evaluation protocol — same data splits, same time budget, same metric per task type, same compute — and obtains comparable per-task scores plus an overall cross-task ranking.

**Why this priority**: This is the central value of the project and the core message of the AMLB paper — a comparison is only meaningful if every framework is measured under provably identical conditions. Without it, nothing else matters.

**Independent Test**: Select at least one dataset per task type (binary, multiclass, regression), run all three frameworks plus baselines under the identical protocol, and produce a results table of per-task scores and an overall ranking. Verify from the recorded run configuration that budget, splits, metric, and resources were the same for every framework.

**Acceptance Scenarios**:

1. **Given** a selected dataset and a fixed protocol (splits, budget, metric, resources), **When** all three frameworks and the baselines are run on it, **Then** each produces a score recorded under demonstrably identical conditions, and the per-framework configuration log proves the conditions matched.
2. **Given** completed runs across all selected datasets, **When** results are aggregated, **Then** an overall ranking is produced that never directly compares incommensurable metrics across task types (e.g., it uses per-task ranks or normalized performance).
3. **Given** a stronger reference baseline (tuned random forest) and a trivial baseline (constant predictor), **When** results are compared, **Then** each framework's standing relative to both baselines is reported per task.

---

### User Story 2 - Failures captured and coverage reported, never hidden (Priority: P2)

When a framework fails on a task (out of memory, exceeds time, chokes on data characteristics, or hits an internal bug), the failure is detected, logged, and categorized, and per-framework coverage (fraction of runs that succeeded) is reported — failures are never silently dropped, because dropping them inflates apparent accuracy.

**Why this priority**: The paper shows that the main cause of failure is dataset size and that silently omitted failures make rankings uninterpretable. Robustness is part of the comparison, not a footnote.

**Independent Test**: Run the benchmark including at least one large/difficult dataset likely to trigger a failure, and verify the failure is recorded with a category and appears in per-framework coverage statistics rather than being absent from the results.

**Acceptance Scenarios**:

1. **Given** a run that exhausts memory or exceeds the time budget, **When** results are collected, **Then** the run is recorded as a categorized failure (memory / time / data / implementation) with its context, not omitted.
2. **Given** a framework that returns a model for some folds of a task but not others, **When** results are aggregated, **Then** the score is reported as mean and standard deviation over completed folds together with the count of folds that returned no result.
3. **Given** all runs are complete, **When** the coverage summary is produced, **Then** each framework shows the fraction of tasks/folds it completed successfully.

---

### User Story 3 - Accuracy vs. inference-time trade-off (Priority: P2)

For every produced model, the benchmark measures inference time and presents the accuracy-versus-inference-time trade-off, identifying which frameworks are Pareto-optimal — because the most accurate model is often the slowest to serve, which matters in practice.

**Why this priority**: The paper finds inference times spanning orders of magnitude; accuracy in isolation misrepresents real-world utility.

**Independent Test**: For completed runs, record both predictive score and inference time, produce a trade-off (Pareto) plot/table, and confirm the Pareto-optimal frameworks are identified.

**Acceptance Scenarios**:

1. **Given** completed models, **When** inference time is measured under the same conditions, **Then** each model has a recorded accuracy and inference-time pair.
2. **Given** the accuracy/inference-time pairs, **When** the trade-off is plotted, **Then** Pareto-optimal frameworks are marked and dominated ones are distinguishable.

---

### User Story 4 - How rankings shift with data characteristics (Priority: P3)

The researcher analyzes how the relative ranking of frameworks changes with dataset characteristics — at minimum dataset size, feature dimensionality, and class balance — to surface each framework's strengths and weaknesses.

**Why this priority**: Average ranks alone hide that frameworks win in different regimes; the paper uses data-characteristic subsets (and Bradley-Terry trees) to reveal this.

**Independent Test**: Group results by a characteristic (e.g., small vs. large datasets) and show whether and how the ranking differs between groups, backed by the recorded numbers.

**Acceptance Scenarios**:

1. **Given** results across datasets of varying size/dimensionality/class balance, **When** grouped by a characteristic, **Then** per-group rankings are produced and differences are reported.
2. **Given** a characteristic where one framework dominates, **When** the analysis is presented, **Then** the regime in which each framework is strongest is stated explicitly.

---

### User Story 5 - One-command reproducibility and a thesis report (Priority: P3)

A documented configuration/command re-runs the benchmark (or a defined subset) and regenerates the result tables and plots from recorded data, and a written report presents the findings, cites the AMLB paper, and states explicitly which pitfalls were avoided and how.

**Why this priority**: Reproducibility is non-negotiable for a thesis and is the headline contribution of the AMLB tool; the report is the graded artifact.

**Independent Test**: From a clean environment, follow the documented steps to re-run a defined subset and regenerate the same tables/plots; confirm a report exists with citations and an explicit pitfalls-avoided section.

**Acceptance Scenarios**:

1. **Given** the recorded configuration and data, **When** the documented re-run command is executed in a clean environment, **Then** the headline result tables and plots are regenerated, with rankings matching within recorded variance.
2. **Given** the finished analysis, **When** the report is reviewed, **Then** it cites the AMLB paper and lists each known pitfall (unequal budgets, inconsistent metrics, ignored failures, no environment isolation) with how this benchmark avoided it.

---

### Edge Cases

- **Out of memory / time exceeded** on large datasets → recorded as a memory/time failure with context; excluded from that task's score aggregate but counted in coverage.
- **Partial folds**: a framework returns models for some folds but not all → report mean/std over completed folds plus the missing-fold count (never impute a score).
- **Highly imbalanced data** causing an internal validation split to miss a class (the paper observed this on small imbalanced sets) → use stratified splitting where applicable; if still unavoidable, record as a data failure.
- **Unsupported feature types** (e.g., high-cardinality categoricals, missing values) for a given framework → documented per framework; handled consistently or recorded as a data failure.
- **Ranking ties** → a defined tie-handling rule (e.g., average rank) is applied and documented.
- **Cross-task-type aggregation** → the overall ranking must never compare a classification metric directly against a regression metric; per-task ranks or normalized performance are used.
- **Non-determinism**: some frameworks are not fully reproducible even with a fixed seed → repeated folds capture variance and the limitation is documented.
- **Budget adherence**: a framework that stops far before, or overruns, the budget → training duration is recorded so adherence can be reported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The benchmark MUST evaluate exactly three AutoML frameworks under test — H2O AutoML, FLAML, and AutoGluon — plus two reference baselines (a constant predictor and a tuned random forest) on every selected task.
- **FR-002**: The benchmark MUST use a curated set of public tabular datasets covering binary classification, multiclass classification, and regression, deliberately chosen to span a range of dataset sizes, feature dimensionality, and class balance; the dataset selection and its source identifiers MUST be recorded.
- **FR-003**: The benchmark MUST apply an identical evaluation protocol to every framework on every task: the same cross-validation splits, the same per-task time budget, the same task-type-appropriate metric (a ranking/probability metric for binary, a multiclass-appropriate metric for multiclass, an error metric for regression), and the same allotted compute resources.
- **FR-004**: The benchmark MUST evaluate at a primary time budget and MUST support at least one larger time budget so the effect of budget on results can be studied.
- **FR-005**: The benchmark MUST run each framework end-to-end (environment setup, data preparation, training within the budget, prediction, scoring) without manual per-framework intervention during a run, and MUST record, for every run, the exact configuration: random seed(s), framework version, dataset version/identifier, time budget, and resource limits.
- **FR-006**: The benchmark MUST detect, record, and categorize run failures into memory, time, data, and implementation categories, and MUST report per-framework coverage (the fraction of tasks/folds completed successfully); failures MUST NOT be silently omitted from the results.
- **FR-007**: The benchmark MUST report, per framework and per task, predictive performance as mean and standard deviation across folds, including the count of folds that returned no result.
- **FR-008**: The benchmark MUST produce an overall cross-task ranking of the frameworks that never directly compares incommensurable metrics across task types (e.g., via per-task ranks or normalized/scaled performance from a baseline to the best observed result).
- **FR-009**: The benchmark MUST measure the inference time of each produced model and present the accuracy-versus-inference-time trade-off, identifying which frameworks are Pareto-optimal.
- **FR-010**: The benchmark MUST analyze how the relative ranking of frameworks changes with data characteristics — at minimum dataset size, dimensionality, and class balance — via grouped comparisons.
- **FR-011**: The benchmark MUST be reproducible: a single documented configuration/command MUST re-run the benchmark (or a defined subset) and regenerate the result tables and plots from recorded data.
- **FR-012**: The benchmark MUST produce a written report that presents the findings, cites the AMLB paper, and explicitly states which known benchmarking pitfalls were avoided and how.
- **FR-013**: The benchmark MUST keep comparisons fair by running each framework with its intended preset(s) and NOT hand-tuning the frameworks' own configuration beyond documented settings that are applied equally to all.
- **FR-014**: The benchmark MUST guarantee no data leakage — test/validation partitions MUST never be used for training or model selection, and the partitioning MUST be identical across all frameworks for a given task.
- **FR-015**: Training duration per run MUST be recorded so that each framework's adherence to the specified time budget can be reported.

### Key Entities *(include if feature involves data)*

- **Framework under test**: one of the three AutoML systems being compared — name, version, preset/configuration, and optimization approach.
- **Baseline**: a reference predictor for context — the constant predictor and the tuned random forest.
- **Task (dataset)**: a public tabular dataset and its prediction target — source identifier, task type (binary/multiclass/regression), number of instances, number of features, and class balance/ratio.
- **Evaluation protocol**: the fixed conditions shared by all runs — cross-validation scheme (folds), time budget(s), compute resources, and the metric used per task type.
- **Run**: a single (framework × task × fold) execution — status (success or failure category), predictive score, training duration, inference time, seed, and versions.
- **Result record**: the aggregation per (framework × task) — mean/std score, completed-fold count, and coverage.
- **Failure**: a recorded unsuccessful run — category (memory / time / data / implementation), message, and context.
- **Report & artifacts**: the produced outputs — result tables, plots (overall ranking, accuracy/inference-time trade-off, ranking-by-characteristic), the reproducibility guide, and the written report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of planned (framework × task × fold) runs end either with a recorded score or with a categorized failure — zero silently missing results.
- **SC-002**: For every task, all frameworks are verifiably evaluated under identical conditions (same folds, same budget, same metric, same resources), confirmable from the recorded run configuration.
- **SC-003**: The benchmark covers at least 10 datasets spanning all three task types (binary, multiclass, regression) and at least three distinct dataset-size tiers.
- **SC-004**: A person other than the author can regenerate the headline results (overall ranking and accuracy/inference-time trade-off tables/plots) from the documented configuration in a clean environment, with rankings matching within the recorded variance.
- **SC-005**: The analysis answers all three core questions — which framework is best overall, how the ranking shifts by data characteristics, and the accuracy/inference-time trade-off — each supported by the recorded numbers.
- **SC-006**: The report identifies at least the four pitfall classes highlighted by the paper (unequal time budgets, inconsistent metrics, ignored failures, no environment isolation) and documents how each was avoided.
- **SC-007**: Per-framework coverage (fraction of successful runs) is reported for all three frameworks and both baselines.

## Assumptions

- Public tabular datasets (preferably reusing the standardized task identifiers from the AMLB OpenML benchmark suite) are accessible and licensed for research use; a real-world dataset (e.g., customer churn) may optionally be added for flavor.
- GPU/cloud compute is available; dataset count and time budgets are scoped to the available time/compute — target roughly 10–15 datasets, a primary budget on the order of one hour per task, and at least one larger budget run.
- The three frameworks and the two baselines are run with their intended/default presets; AutoGluon's higher-quality preset may be used given GPU availability.
- Cross-validation uses a fixed number of folds (default 10, matching the paper) applied identically to all frameworks.
- Some AutoML frameworks are not fully deterministic even with a fixed seed; repeated folds capture variance and this limitation is documented rather than eliminated.
- The specific orchestration tooling and environment-isolation mechanism (whether to adopt an existing open-source benchmark runner or build a custom harness, the containerization approach, and the languages/libraries used) is an implementation decision deferred to the planning phase.
- Scope is tabular supervised learning only; unstructured data (images, text), Neural Architecture Search, building or modifying an AutoML framework, production deployment/serving, and an end-user application UI are explicitly out of scope.
- The project's governing principles of reproducibility, no data leakage, evaluation-against-baseline, and simplicity (constitution principles II–V) apply directly; the medical-safety principle (I) and medical-specific technical constraints do not apply to this benchmark feature and should be scoped out or addressed via a feature-specific constitution during planning.
