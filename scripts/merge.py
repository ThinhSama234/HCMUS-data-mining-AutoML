"""
Merge partial run files from distributed machines into one complete report.

Usage:
    python scripts/merge.py reports/partial_flaml.json reports/partial_autogluon.json
    python scripts/merge.py reports/partial_*.json --output reports/run_merged.json
"""
from __future__ import annotations

import argparse
import json
import math
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path("reports")


def aggregate(jobs: list[dict]) -> dict:
    groups: dict[tuple, list] = defaultdict(list)
    for job in jobs:
        if job["status"] == "done":
            groups[(job["dataset"], job["framework"])].append(job.get("metric_score", 0))

    summary = []
    for (ds, fw), scores in groups.items():
        n    = len(scores)
        mean = sum(scores) / n
        std  = math.sqrt(sum((s - mean) ** 2 for s in scores) / max(n - 1, 1))
        summary.append({
            "dataset":             ds,
            "framework":           fw,
            "n_folds":             n,
            "metric_score_mean":   round(mean, 6),
            "metric_score_std":    round(std,  6),
            "scores_per_fold":     [round(s, 6) for s in scores],
        })
    return {"summary": sorted(summary, key=lambda r: (r["dataset"], r["framework"]))}


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge partial benchmark reports")
    parser.add_argument("inputs", nargs="+", help="Partial run JSON files to merge")
    parser.add_argument("--output", default=None,
                        help="Output path (default: reports/run_merged_<id>.json)")
    args = parser.parse_args()

    input_paths = [Path(p) for p in args.inputs]
    for p in input_paths:
        if not p.exists():
            print(f"  ERROR: file not found: {p}")
            return

    # load all partial runs
    runs = [json.loads(p.read_text()) for p in input_paths]
    print(f"Merging {len(runs)} file(s):")
    for p, r in zip(input_paths, runs):
        n_done = sum(1 for j in r["jobs"] if j["status"] == "done")
        print(f"  {p.name}  —  {n_done}/{len(r['jobs'])} jobs done")

    # index jobs by (dataset, framework, fold) — "done" wins over "pending"/"failed"
    merged_jobs: dict[tuple, dict] = {}
    for run in runs:
        for job in run["jobs"]:
            key = (job["dataset"], job["framework"], job["fold"])
            existing = merged_jobs.get(key)
            if existing is None or job["status"] == "done":
                merged_jobs[key] = job

    jobs = sorted(merged_jobs.values(), key=lambda j: (j["dataset"], j["framework"], j["fold"]))

    # pick metadata from first run, override with merge info
    base = runs[0]
    merged_run = {
        "run_id":       "merged_" + uuid.uuid4().hex[:6],
        "merged_from":  [r["run_id"] for r in runs],
        "time_budget":  base["time_budget"],
        "frameworks":   sorted({fw for r in runs for fw in r.get("frameworks", [])}),
        "datasets":     sorted({ds for r in runs for ds in r.get("datasets", [])}),
        "started_at":   min(r["started_at"] for r in runs),
        "merged_at":    datetime.now().isoformat(),
        "jobs":         jobs,
    }
    merged_run.update(aggregate(jobs))

    done   = sum(1 for j in jobs if j["status"] == "done")
    failed = sum(1 for j in jobs if j["status"] == "failed")
    total  = len(jobs)

    out = Path(args.output) if args.output else \
          REPORT_DIR / f"run_{merged_run['run_id']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(merged_run, indent=2, default=str))

    print(f"\ndone={done}  failed={failed}  total={total}")
    print(f"merged report → {out}")


if __name__ == "__main__":
    main()
