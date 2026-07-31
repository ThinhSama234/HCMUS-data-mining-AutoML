"""
Orchestrator — dispatches one worker.py subprocess per (framework × dataset × fold),
collects results into a single structured run file, and supports resume.

Usage:
    python scripts/orchestrator.py                          # new run, all frameworks
    python scripts/orchestrator.py --run-id 20260701_abc   # resume
    python scripts/orchestrator.py --frameworks flaml h2o  # subset of frameworks
    python scripts/orchestrator.py --datasets breast_cancer wine
    python scripts/orchestrator.py --time-budget 3600
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DATASET_DIR = Path("dataset")
REPORT_DIR  = Path("reports")
TMP_DIR     = REPORT_DIR / "tmp"
ENVS_DIR    = Path("envs") / "venvs"

ALL_FRAMEWORKS = ["flaml", "autogluon", "h2o", "lightautoml", "mljar", "dummy", "randomforest"]

# frameworks that share the baselines venv
BASELINE_FRAMEWORKS = {"dummy", "randomforest"}

TIME_BUDGET = 3600  # seconds per (framework × dataset × fold)


# ── helpers ───────────────────────────────────────────────────────────────────

def python_for(framework: str, no_venv: bool = False) -> str:
    """Return path to the venv python for a given framework."""
    if no_venv:
        return sys.executable   # use the current Python (e.g. on Kaggle)
    venv = ENVS_DIR / ("baselines" if framework in BASELINE_FRAMEWORKS else framework)
    if sys.platform == "win32":
        return str(venv / "Scripts" / "python.exe")
    return str(venv / "bin" / "python")


def load_datasets(names: list[str] | None) -> list[dict]:
    datasets = []
    for folder in sorted(DATASET_DIR.iterdir()):
        if not folder.is_dir():
            continue
        if names and folder.name not in names:
            continue
        if not (folder / "train.csv").exists():
            continue
        if not (folder / "meta.json").exists():
            continue
        if not (folder / "folds.json").exists():
            print(f"  [warn] {folder.name}: missing folds.json — run gen_folds.py first")
            continue
        meta     = json.loads((folder / "meta.json").read_text())
        n_splits = json.loads((folder / "folds.json").read_text())["n_splits"]
        datasets.append({"name": folder.name, "path": str(folder),
                         "n_folds": n_splits, **meta})
    return datasets


# ── run file ──────────────────────────────────────────────────────────────────

def _save(run: dict, path: Path) -> None:
    path.write_text(json.dumps(run, indent=2, default=str))


def init_run(run_id: str, time_budget: int, frameworks: list,
             datasets: list, max_folds: int | None = None,
             folds_filter: set | None = None) -> tuple[dict, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)
    run_file = REPORT_DIR / f"run_{run_id}.json"

    if run_file.exists():
        print(f"Resuming run: {run_id}")
        return json.loads(run_file.read_text()), run_file

    print(f"New run: {run_id}")
    jobs = [
        {
            "dataset":   ds["name"],
            "framework": fw,
            "fold":      fold,
            "status":    "pending",
            "task":      ds.get("task"),
            "label":     ds.get("label"),
        }
        for ds in datasets
        for fw in frameworks
        for fold in range(min(ds["n_folds"], max_folds or ds["n_folds"]))
        if folds_filter is None or fold in folds_filter
    ]
    run = {
        "run_id":      run_id,
        "time_budget": time_budget,
        "frameworks":  frameworks,
        "datasets":    [d["name"] for d in datasets],
        "started_at":  datetime.now().isoformat(),
        "jobs":        jobs,
    }
    _save(run, run_file)
    return run, run_file


# ── dispatch one job ──────────────────────────────────────────────────────────

def run_job(job: dict, time_budget: int, run_id: str, no_venv: bool = False) -> dict:
    fw      = job["framework"]
    ds      = job["dataset"]
    fold    = job["fold"]
    out     = TMP_DIR / f"{run_id}_{ds}_{fw}_fold{fold}.json"
    python  = python_for(fw, no_venv)

    cmd = [
        python, "scripts/worker.py",
        "--framework",   fw,
        "--dataset-dir", str(DATASET_DIR / ds),
        "--fold",        str(fold),
        "--time-budget", str(time_budget),
        "--output",      str(out),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=time_budget + 120)
        if out.exists():
            result = json.loads(out.read_text())
            out.unlink(missing_ok=True)   # clean up tmp file
            return result
        # worker didn't write output — treat as impl failure
        return {**job, "status": "failed", "failure_type": "impl",
                "error": proc.stderr[-500:] if proc.stderr else "no output written"}
    except subprocess.TimeoutExpired:
        return {**job, "status": "failed", "failure_type": "timeout",
                "error": f"subprocess timeout after {time_budget + 120}s"}
    except FileNotFoundError:
        return {**job, "status": "failed", "failure_type": "impl",
                "error": f"python not found: {python}  (run envs/setup.bat first)"}


# ── progress / ETA ───────────────────────────────────────────────────────────

def _fmt(seconds: float) -> str:
    """Format seconds as Xh Ym Zs."""
    seconds = max(0, int(seconds))
    h, r  = divmod(seconds, 3600)
    m, s  = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _eta_line(run_start: float, completed: int, remaining: int) -> str:
    elapsed = time.perf_counter() - run_start
    if completed == 0:
        return f"  elapsed={_fmt(elapsed)}  remaining≈unknown"
    avg          = elapsed / completed
    remaining_s  = avg * remaining
    finish_clock = datetime.now() + timedelta(seconds=remaining_s)
    return (f"  elapsed={_fmt(elapsed)}  "
            f"remaining≈{_fmt(remaining_s)}  "
            f"ETA {finish_clock.strftime('%H:%M')} ({finish_clock.strftime('%b %d')})")


# ── aggregate fold results ────────────────────────────────────────────────────

def aggregate(run: dict) -> dict:
    """Compute mean ± std per (dataset × framework) across folds."""
    from collections import defaultdict
    import math

    groups: dict[tuple, list] = defaultdict(list)
    for job in run["jobs"]:
        if job["status"] == "done":
            groups[(job["dataset"], job["framework"])].append(job.get("metric_score", 0))

    summary = []
    for (ds, fw), scores in groups.items():
        n    = len(scores)
        mean = sum(scores) / n
        std  = math.sqrt(sum((s - mean) ** 2 for s in scores) / max(n - 1, 1))
        summary.append({
            "dataset":        ds,
            "framework":      fw,
            "n_folds":        n,
            "metric_score_mean": round(mean, 6),
            "metric_score_std":  round(std,  6),
            "scores_per_fold":   [round(s, 6) for s in scores],
        })
    return {"summary": sorted(summary, key=lambda r: (r["dataset"], r["framework"]))}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AutoML benchmark orchestrator")
    parser.add_argument("--run-id",      default=None)
    parser.add_argument("--time-budget", type=int, default=TIME_BUDGET)
    parser.add_argument("--frameworks",  nargs="+", default=None,
                        choices=ALL_FRAMEWORKS,
                        help="Subset of frameworks to run (default: all)")
    parser.add_argument("--datasets",    nargs="+", default=None,
                        help="Subset of dataset names to run (default: all)")
    parser.add_argument("--max-folds",   type=int,   default=None,
                        help="Cap number of folds per (dataset × framework), e.g. 1 for smoke test")
    parser.add_argument("--folds",       nargs="+",  type=int, default=None,
                        help="Specific fold indices to run, e.g. --folds 0 1 2 (for distributed runs)")
    parser.add_argument("--no-venv",     action="store_true",
                        help="Use current Python instead of venvs (for Kaggle / pre-installed envs)")
    args = parser.parse_args()

    frameworks = args.frameworks or ALL_FRAMEWORKS
    datasets   = load_datasets(args.datasets)

    if not datasets:
        print("No datasets found. Add CSVs under dataset/<name>/ and run gen_folds.py.")
        return

    print(f"Datasets  : {[d['name'] for d in datasets]}")
    print(f"Frameworks: {frameworks}")
    print(f"Budget    : {args.time_budget}s per fold")

    run_id        = args.run_id or (datetime.now().strftime("%Y%m%d_%H%M%S")
                                    + "_" + uuid.uuid4().hex[:6])
    folds_filter  = set(args.folds) if args.folds else None
    run, run_file = init_run(run_id, args.time_budget, frameworks, datasets,
                             args.max_folds, folds_filter)

    total      = len(run["jobs"])
    done       = sum(1 for j in run["jobs"] if j["status"] == "done")
    failed     = sum(1 for j in run["jobs"] if j["status"] == "failed")
    pending    = total - done - failed
    run_start  = time.perf_counter()
    completed  = 0   # jobs finished in THIS session (for ETA calc)

    for i, job in enumerate(run["jobs"], 1):
        tag = f"[{i}/{total}] {job['dataset']} × {job['framework']} fold {job['fold']}"

        if job["status"] in ("done", "failed"):
            print(f"  skip  {tag}  ({job['status']})")
            continue

        print(f"  run   {tag} ...", flush=True)
        result = run_job(job, run["time_budget"], run_id, args.no_venv)

        job.update(result)
        _save(run, run_file)   # write after every job — crash-safe resume
        completed += 1
        remaining  = pending - completed

        if job["status"] == "done":
            metric    = job.get("metric_name", "score")
            score_raw = job.get("metric_score_raw", job.get("metric_score", "?"))
            direction = "↓" if job.get("metric_direction") == "lower_is_better" else "↑"
            print(f"  done  {tag}  {metric}={score_raw} {direction}")
            done += 1
        else:
            ftype = job.get("failure_type", "?")
            print(f"  FAIL  {tag}  type={ftype}  {str(job.get('error',''))[:120]}")
            failed += 1

        print(_eta_line(run_start, completed, remaining))

    # attach aggregate summary
    run.update(aggregate(run))
    run["completed_at"] = datetime.now().isoformat()
    _save(run, run_file)

    coverage = done / total * 100 if total else 0
    print(f"\n{'─'*60}")
    print(f"  done={done}  failed={failed}  total={total}  coverage={coverage:.1f}%")
    print(f"  report → {run_file}")


if __name__ == "__main__":
    main()
