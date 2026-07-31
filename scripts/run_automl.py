"""
AutoML benchmark runner.

Scans dataset/*/ for train.csv + meta.json, runs each framework on each dataset,
and logs results to a single structured JSON report per run.

Usage:
    python scripts/run_automl.py                          # new run
    python scripts/run_automl.py --run-id 20260701_abc   # resume
    python scripts/run_automl.py --time-budget 120        # 2 min per combo
"""
from __future__ import annotations

import argparse
import json
import time
import tracemalloc
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_squared_error, roc_auc_score
from sklearn.model_selection import train_test_split

DATASET_DIR = Path("dataset")
REPORT_DIR  = Path("reports")
FRAMEWORKS  = [
    "flaml",
    "autogluon",
    "h2o",   # requires Java — uncomment when Java is available
]
TIME_BUDGET = 60          # seconds per (dataset × framework)

DEFAULT_METRIC = {
    "classification": None,  # auto: "auc" if binary, "log_loss" if multiclass
    "regression":     "rmse",
}

# score stored internally as "higher is better"; raw_fn converts back to natural value
METRIC_META = {
    "auc":      {"direction": "higher_is_better", "raw_fn": lambda s: s},
    "log_loss": {"direction": "lower_is_better",  "raw_fn": lambda s: -s},
    "rmse":     {"direction": "lower_is_better",  "raw_fn": lambda s: -s},
    "accuracy": {"direction": "higher_is_better", "raw_fn": lambda s: s},
}

# user-facing name → framework internal name
_FLAML_METRIC = {
    "auc":      "roc_auc",
    "log_loss": "log_loss",
    "rmse":     "rmse",
    "accuracy": "accuracy",
}

_AG_METRIC = {
    "auc":      "roc_auc",
    "log_loss": "log_loss",
    "rmse":     "rmse",
    "accuracy": "accuracy",
}


# ── data ─────────────────────────────────────────────────────────────────────

def load_datasets() -> list[dict]:
    datasets = []
    for folder in sorted(DATASET_DIR.iterdir()):
        if not folder.is_dir():
            continue
        train_csv = folder / "train.csv"
        meta_json = folder / "meta.json"
        if not (train_csv.exists() and meta_json.exists()):
            continue
        meta = json.loads(meta_json.read_text())
        meta["name"]      = folder.name
        meta["train_csv"] = train_csv
        meta.setdefault("drop_cols", [])
        meta.setdefault("metric", DEFAULT_METRIC[meta["task"]])
        datasets.append(meta)
    return datasets


# ── metrics ──────────────────────────────────────────────────────────────────

def compute_score(y_true, y_pred, y_proba, metric: str) -> float:
    if metric == "auc":
        proba = y_proba[:, 1] if y_proba.ndim > 1 else y_proba
        return float(roc_auc_score(y_true, proba))
    if metric == "log_loss":
        return float(-log_loss(y_true, y_proba))
    if metric == "rmse":
        return float(-np.sqrt(mean_squared_error(y_true, y_pred)))
    if metric == "accuracy":
        return float((np.asarray(y_true) == np.asarray(y_pred)).mean())
    raise ValueError(f"Unknown metric: {metric}")


# ── framework runners ─────────────────────────────────────────────────────────

def _run_flaml(X_train, y_train, X_test, y_test, task, metric, time_budget) -> dict:
    from flaml import AutoML  # imported here so missing install = clear error

    automl = AutoML()
    automl.fit(
        X_train, y_train,
        task=task,
        metric=_FLAML_METRIC.get(metric, metric),
        time_budget=time_budget,
        verbose=0,
    )
    y_pred  = automl.predict(X_test)
    y_proba = automl.predict_proba(X_test) if task == "classification" else None
    return {
        "metric_score": round(compute_score(y_test.values, y_pred, y_proba, metric), 6),
        "best_model":   automl.best_estimator,
        "best_config":  automl.best_config,
    }


def _run_autogluon(X_train, y_train, X_test, y_test, task, metric, time_budget) -> dict:
    import tempfile
    from autogluon.tabular import TabularPredictor

    _LABEL = "__target__"
    train_df = X_train.copy()
    train_df[_LABEL] = y_train.values

    with tempfile.TemporaryDirectory() as tmp:
        predictor = TabularPredictor(
            label=_LABEL,
            eval_metric=_AG_METRIC.get(metric, metric),
            path=tmp,
            verbosity=0,
        )
        predictor.fit(train_df, time_limit=time_budget)

        y_pred  = predictor.predict(X_test).values
        y_proba = predictor.predict_proba(X_test).values if task == "classification" else None
        board   = predictor.leaderboard(silent=True)
        best    = board.iloc[0]["model"] if not board.empty else "unknown"

    return {
        "metric_score": round(compute_score(y_test.values, y_pred, y_proba, metric), 6),
        "best_model":   best,
        "best_config":  {},
    }


def _run_h2o(X_train, y_train, X_test, y_test, task, metric, time_budget) -> dict:
    import h2o
    from h2o.automl import H2OAutoML

    _H2O_METRIC = {
        "auc":      "AUC",
        "log_loss": "logloss",
        "rmse":     "RMSE",
        "accuracy": "mean_per_class_error",
    }

    h2o.init(verbose=False)  # connects to existing cluster if already running

    _LABEL = "__target__"
    train_df = X_train.copy()
    train_df[_LABEL] = y_train.values

    train_h2o = h2o.H2OFrame(train_df)
    test_h2o  = h2o.H2OFrame(X_test)

    if task == "classification":
        train_h2o[_LABEL] = train_h2o[_LABEL].asfactor()

    aml = H2OAutoML(
        max_runtime_secs=time_budget,
        sort_metric=_H2O_METRIC.get(metric, metric),
        seed=42,
        verbosity=None,
    )
    aml.train(y=_LABEL, training_frame=train_h2o)

    preds  = aml.leader.predict(test_h2o).as_data_frame()
    y_pred = preds["predict"].values
    # columns after "predict" are class probabilities (p0, p1, ... for classification)
    y_proba = preds.iloc[:, 1:].values if task == "classification" else None

    return {
        "metric_score": round(compute_score(y_test.values, y_pred, y_proba, metric), 6),
        "best_model":   aml.leader.model_id,
        "best_config":  {},
    }


RUNNERS: dict[str, callable] = {
    "flaml":     _run_flaml,
    "autogluon": _run_autogluon,
    "h2o":       _run_h2o,
}


# ── single combo ─────────────────────────────────────────────────────────────

def run_one(ds_meta: dict, framework: str, time_budget: int) -> dict:
    df = pd.read_csv(ds_meta["train_csv"])
    label     = ds_meta["label"]
    task      = ds_meta["task"]
    drop_cols = [c for c in ds_meta.get("drop_cols", []) if c in df.columns]

    df = df.drop(columns=drop_cols)
    X  = df.drop(columns=[label])
    y  = df[label]

    # resolve metric now that we know the data
    metric = ds_meta["metric"]
    if metric is None:
        metric = "auc" if y.nunique() == 2 else "log_loss"

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # tracemalloc tracks Python-level allocs; C-extension memory (numpy/lgbm)
    # is not captured — treat peak_memory_mb as a lower bound.
    tracemalloc.start()
    t0     = time.perf_counter()
    result = RUNNERS[framework](X_train, y_train, X_test, y_test, task, metric, time_budget)
    duration  = time.perf_counter() - t0
    _, peak   = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    meta = METRIC_META.get(metric, {"direction": "higher_is_better", "raw_fn": lambda s: s})
    result["metric_name"]      = metric
    result["metric_direction"] = meta["direction"]
    result["metric_score_raw"] = round(meta["raw_fn"](result["metric_score"]), 6)
    result["resource_usage"] = {
        "duration_s":     round(duration, 2),
        "peak_memory_mb": round(peak / 1024 / 1024, 2),
    }
    return result


# ── run file ─────────────────────────────────────────────────────────────────

def _save(run: dict, path: Path) -> None:
    path.write_text(json.dumps(run, indent=2, default=str))


def init_run(run_id: str, time_budget: int, frameworks: list, datasets: list) -> tuple[dict, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    run_file = REPORT_DIR / f"run_{run_id}.json"

    if run_file.exists():
        print(f"Resuming run: {run_id}")
        return json.loads(run_file.read_text()), run_file

    print(f"New run: {run_id}")
    results = [
        {
            "dataset":     ds["name"],
            "framework":   fw,
            "status":      "pending",
            "label":       ds["label"],
            "task":        ds["task"],
            "metric_name": ds.get("metric"),  # may still be None, resolved in run_one
        }
        for ds in datasets
        for fw in frameworks
    ]
    run = {
        "run_id":      run_id,
        "time_budget": time_budget,
        "frameworks":  frameworks,
        "started_at":  datetime.now().isoformat(),
        "results":     results,
    }
    _save(run, run_file)
    return run, run_file


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AutoML benchmark runner")
    parser.add_argument("--run-id",      default=None,        help="Resume a previous run ID")
    parser.add_argument("--time-budget", type=int, default=TIME_BUDGET,
                        help="Seconds per framework per dataset")
    args = parser.parse_args()

    datasets = load_datasets()
    if not datasets:
        print(f"No datasets found in {DATASET_DIR}/  (each needs train.csv + meta.json)")
        return

    print(f"Datasets  : {[d['name'] for d in datasets]}")
    print(f"Frameworks: {FRAMEWORKS}")

    run_id        = args.run_id or (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
    run, run_file = init_run(run_id, args.time_budget, FRAMEWORKS, datasets)
    ds_map        = {ds["name"]: ds for ds in datasets}
    total         = len(run["results"])

    for i, entry in enumerate(run["results"], 1):
        tag = f"[{i}/{total}] {entry['dataset']} × {entry['framework']}"

        if entry["status"] == "done":
            print(f"  skip  {tag}")
            continue

        print(f"  run   {tag} ...", flush=True)
        try:
            result = run_one(ds_map[entry["dataset"]], entry["framework"], run["time_budget"])
            entry.update(result)
            entry["status"]       = "done"
            entry["completed_at"] = datetime.now().isoformat()
            entry["error"]        = None
        except Exception as e:
            entry["status"]       = "failed"
            entry["error"]        = str(e)
            entry["completed_at"] = datetime.now().isoformat()
            print(f"  FAIL  {e}")

        _save(run, run_file)  # save after every entry so crash = safe resume

    done = sum(1 for r in run["results"] if r["status"] == "done")
    print(f"\n{done}/{total} done. Report → {run_file}")


if __name__ == "__main__":
    main()
