# Contract: analysis outputs → report

What `analysis/` produces and the report consumes. Each output is regenerable from the results CSV by one command (FR-011).

## Rankings table (FR-008, SC-005)
- **Shape**: rows = frameworks+baselines; columns = average rank **per task type** and overall (ranks computed within task, then averaged; metrics never mixed across types).
- **Backs**: "which framework is best overall."

## Coverage table (FR-006, SC-001, SC-007)
- **Shape**: rows = frameworks+baselines; columns = success rate, and failure counts by category (memory / time / data / implementation).
- **Backs**: robustness; proves no run was silently dropped.

## Pareto table + plot (FR-009, SC-005)
- **Shape**: per framework, median predictive score vs median `predict_duration`; flag Pareto-optimal frameworks.
- **Backs**: accuracy ↔ inference-time trade-off.

## By-characteristic table (FR-010, SC-005)
- **Shape**: rankings grouped by dataset `size_tier`, `dim_tier`, `balance_tier`.
- **Backs**: "how the ranking shifts with data characteristics."

## Reproducibility guide + report (FR-011, FR-012, SC-004, SC-006)
- One documented command re-runs a defined subset and regenerates all of the above.
- Report cites AMLB and lists the four pitfalls (unequal budgets, inconsistent metrics, ignored failures, no isolation) with how each was avoided.
