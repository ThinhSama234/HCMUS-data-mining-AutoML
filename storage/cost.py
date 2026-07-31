"""Cost estimator (spec 007) — extracted from console/views/cost.py so the console and the API
share ONE implementation (no duplication).

Real upper-bound formula (no cloud calls): a constraint sets the per (dataset × fold) time budget;
total compute_hours = datasets × frameworks × folds × budget_seconds / 3600, costed against each
compute instance's hourly rate.
"""
from __future__ import annotations

from storage import repo, runner


def estimate(n_datasets, n_frameworks, constraint=None, eng=None) -> dict:
    constraint = constraint or runner.DEFAULT_CONSTRAINT
    info = runner.constraint_info(constraint, eng) or {"folds": 1, "seconds": 60, "cores": 4}
    folds = info["folds"] or 1
    budget_s = info["seconds"] or 0
    cores = info["cores"]
    n_datasets = max(int(n_datasets or 0), 0)
    n_frameworks = max(int(n_frameworks or 0), 0)
    total_runs = n_datasets * n_frameworks * folds
    compute_hours = total_runs * budget_s / 3600.0

    by_instance = []
    inst = repo.list_instances()
    if inst is not None and not inst.empty:
        for _, r in inst.sort_values("rate_per_hour").iterrows():
            rate = float(r["rate_per_hour"] or 0)
            by_instance.append({
                "name": r["name"],
                "vcpus": int(r["vcpus"]) if r["vcpus"] else None,
                "memory_gb": int(r["memory_gb"]) if r["memory_gb"] else None,
                "gpu_type": r["gpu_type"] or None,
                "rate_per_hour": rate,
                "est_cost": round(compute_hours * rate, 2),
            })
    return {
        "constraint": constraint, "folds": folds, "budget_seconds": budget_s, "cores": cores,
        "total_runs": total_runs, "compute_hours": round(compute_hours, 3),
        "by_instance": by_instance,
    }
