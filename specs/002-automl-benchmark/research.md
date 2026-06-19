# Phase 0 Research: AutoML Framework Benchmark

All decisions below are made to reach a **correct** MVP (User Story 1) **fastest**. No open `NEEDS CLARIFICATION` remain.

## D1 — Orchestration harness: reuse the AMLB tool

- **Decision**: Use the official `automlbenchmark` (AMLB) tool as the harness; do not build a custom one.
- **Rationale**: AMLB already enforces the identical protocol that defines a fair comparison (fixed OpenML folds, equal time budgets, per-task metrics, controlled CPU/memory), integrates all three frameworks plus the baselines, captures and categorizes failures, and emits a tidy results CSV. It is the paper's own tool → maximal "based on this paper" and reproducibility, and the fastest route to a correct MVP.
- **Alternatives considered**: Custom harness calling each library's Python API directly — rejected: slower to build and it re-introduces the exact pitfalls (budget/metric/split drift, silent failures) the thesis is about. Kept as a fallback only if a framework version is unsupported by AMLB.

## D2 — Runner mode: local for MVP, Docker for final

- **Decision**: Run the MVP smoke test in AMLB **local mode** (`-m local`); run the final thesis numbers in **Docker mode** (`-m docker`).
- **Rationale**: Local mode gives the first end-to-end result with zero image-build overhead — fastest MVP. Docker mode pins the full software stack per framework for reproducibility (constitution II) and clean resource isolation for the reported runs.
- **Alternatives considered**: AWS mode (`-m aws`) — deferred; useful only when parallelizing the full suite across many instances. Docker-only from day one — rejected: image setup slows the first result.

## D3 — Datasets: reuse OpenML task IDs from the paper

- **Decision**: Select datasets from the AMLB OpenML suites (Appendix A of the paper) by task ID, so identity, splits, and licensing are known.
- **MVP-3 (smoke, one per task type, all small)**:
  - Binary: `credit-g` — OpenML task **168757** (n=1000, p=21).
  - Multiclass: `vehicle` — task **190146** (n=846, 4 classes).
  - Regression: `Moneyball` — task **167210** (n=1232).
- **Thesis-~12 (3 task types × ~3 size tiers; includes an imbalanced + a real-world flavor)**:
  - Binary: `credit-g` (168757, small) · `churn` (359968, n=5000, ratio 0.16 — imbalanced, real-world) · `bank-marketing` (359982, n=45211) · `APSFailure` (168868, n=76000, large, ratio 0.02).
  - Multiclass: `vehicle` (190146, small) · `eucalyptus` (359954, 736, 5 classes) · `connect-4` (359977, 67557) · `helena` (359984, 65196, 100 classes — stress).
  - Regression: `Moneyball` (167210, small) · `house_sales` (359949, 21613) · `elevators` (359936, 16599) · `diamonds` (233211, 53940, large).
- **Rationale**: Reusing the paper's tasks makes the comparison directly comparable to published numbers and removes data-prep risk. The spread over size / dimensionality / class balance is what enables User Story 4.
- **Alternatives considered**: A Kaggle dataset as primary — rejected for the MVP (extra prep, licensing); may be added later as one extra "real-world" task.

## D4 — Budgets and folds

- **Decision**: MVP = ~**10-minute** budget, **1 fold** (single holdout). Final = **1 hour** budget, **10 folds**. Optional **4-hour** budget on a subset to study budget effect (FR-004).
- **Rationale**: 10 min × 1 fold proves the pipeline in hours, not days. 1 h × 10-fold matches the paper's primary setting and gives variance estimates. 4 h is the paper's secondary budget for the effect-of-budget analysis.
- **Alternatives considered**: 10-fold from the start — rejected for MVP (10× slower first result). >4 h — out of scope/compute.

## D5 — Metrics per task type

- **Decision**: Use AMLB's defaults — **AUC** (binary), **log loss** (multiclass), **RMSE** (regression).
- **Rationale**: Matches the spec and the paper; AMLB selects them automatically by task type, guaranteeing the "same metric per task type" requirement (FR-003).
- **Alternatives considered**: Accuracy/F1 for classification — rejected: threshold-dependent and weaker under class imbalance; AUC/log loss are the paper's choices.

## D6 — Frameworks and presets

- **Decision**: `H2OAutoML`, `flaml`, `AutoGluon` (best-quality preset, GPU-enabled) + baselines `constantpredictor`, `RandomForest`, `TunedRandomForest`.
- **Rationale**: The three target frameworks plus the paper's baselines for context (FR-001, IV). AutoGluon best-quality is justified because GPU is available; the paper notes AutoGluon's top average rank.
- **Alternatives considered**: AutoGluon "high-quality (inference-limited)" preset — keep as an optional extra config to enrich the Pareto/inference-time story (US3); not required for MVP.

## D7 — GPU usage

- **Decision**: Use GPU for AutoGluon best-quality; H2O/FLAML run CPU (their default). In Docker mode, use the NVIDIA container runtime; in local mode, rely on the local CUDA install.
- **Rationale**: Honors the "GPU available" decision and the AutoGluon preset; H2O/FLAML gain little from GPU per the paper.
- **Alternatives considered**: GPU for all — unnecessary; H2O/FLAML are CPU-bound.

## D8 — Analysis from the results CSV

- **Decision**: Drive all analysis from the AMLB results CSV with pandas: per-task rank → **average rank** (per task type, never mixing metrics — FR-008); **coverage** = success fraction + failures grouped into memory/time/data/implementation (FR-006); **Pareto** = predictive score vs `predict_duration` (FR-009); **by-characteristic** = join results with each task's n / p / class-ratio and group (FR-010).
- **Rationale**: AMLB records everything needed (result, durations, model count, info/error) in one file → US2/US3/US4 are mostly post-processing, not new runs.
- **Alternatives considered**: AMLB's bundled interactive visualization — use it for exploration, but our scripted analysis is what the report cites (reproducible, version-controlled). Bradley-Terry trees (paper's method for US4) — optional stretch; grouped comparison satisfies FR-010.

## D9 — Failure categorization mapping

- **Decision**: Map AMLB's recorded error/info into the four spec categories: out-of-memory/segfault → **memory**; budget/leniency overrun → **time**; class-missing-in-split / unsupported feature types → **data**; framework code exceptions → **implementation**.
- **Rationale**: Matches the paper's taxonomy (FR-006); makes coverage interpretable.
- **Alternatives considered**: Binary success/fail only — rejected: loses the "why", which the paper shows is the interesting part.

## D10 — Reproducibility mechanism

- **Decision**: Pin everything via the AMLB user dir (benchmark + constraint + framework configs) under version control, fixed seeds, recorded framework/tool versions, Docker images for final runs, and `scripts/run_full.sh` as the single documented re-run command (FR-011, SC-004).
- **Rationale**: A reviewer re-runs one script in a clean container and regenerates the headline tables/plots.
- **Alternatives considered**: Manual notebook steps — rejected: not one-command reproducible.

## Open items to confirm at first setup (non-blocking)

- Exact AMLB install path (clone + `pip install` vs packaged `amlb`) and the precise CLI/flags for `--userdir`, `--mode`, fold/seed overrides, and the built-in short constraint name (e.g., `test`) — confirm against the tool's current docs at setup; the plan does not depend on the exact spelling.
- Current framework versions AMLB resolves (recorded automatically in the results CSV).
