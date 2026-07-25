"""
Single-framework worker — runs ONE (framework × dataset × fold).

Designed to run inside a framework-specific venv so there are no cross-framework
dependency conflicts. Called by orchestrator.py via subprocess.

Usage:
    python scripts/worker.py \
        --framework flaml \
        --dataset-dir dataset/breast_cancer \
        --fold 0 \
        --time-budget 3600 \
        --output reports/tmp/breast_cancer_flaml_fold0.json
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_squared_error, roc_auc_score
from sklearn.model_selection import cross_val_score


# ── metrics ───────────────────────────────────────────────────────────────────

def compute_score(y_true, y_pred, y_proba, metric: str) -> float:
    if metric == "auc":
        if y_proba is not None and y_proba.ndim > 1 and y_proba.shape[1] > 2:
            # multiclass: macro one-vs-rest AUC
            return float(roc_auc_score(y_true, y_proba, multi_class="ovr", average="macro"))
        proba = y_proba[:, 1] if (y_proba is not None and y_proba.ndim > 1) else y_proba
        return float(roc_auc_score(y_true, proba))
    if metric == "accuracy":
        return float((np.asarray(y_true) == np.asarray(y_pred)).mean())
    if metric == "log_loss":
        return float(-log_loss(y_true, y_proba))
    if metric == "rmse":
        return float(-np.sqrt(mean_squared_error(y_true, y_pred)))
    raise ValueError(f"Unknown metric: {metric}")


def get_version(framework: str) -> str:
    pkg_map = {
        "flaml":        "flaml",
        "autogluon":    "autogluon.tabular",
        "h2o":          "h2o",
        "lightautoml":  "lightautoml",
        "mljar":        "mljar-supervised",
        "dummy":        "scikit-learn",
        "randomforest": "scikit-learn",
    }
    try:
        return importlib.metadata.version(pkg_map.get(framework, framework))
    except Exception:
        return "unknown"


# ── framework runners ─────────────────────────────────────────────────────────

def _run_flaml(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    from flaml import AutoML

    _METRIC = {"auc": "roc_auc", "log_loss": "log_loss", "rmse": "rmse", "accuracy": "accuracy"}

    automl = AutoML()
    automl.fit(X_train, y_train, task=task, metric=_METRIC.get(metric, metric),
               time_budget=time_budget, verbose=0)

    t0      = time.perf_counter()
    y_pred  = automl.predict(X_test)
    y_proba = automl.predict_proba(X_test) if task == "classification" else None
    infer_s = time.perf_counter() - t0

    return y_pred, y_proba, infer_s, {"best_model": automl.best_estimator, "best_config": automl.best_config}


def _run_autogluon(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    import tempfile
    from autogluon.tabular import TabularPredictor

    _METRIC = {
        "auc":      "roc_auc",
        "log_loss": "log_loss",
        "rmse":     "root_mean_squared_error",  # AG name differs from sklearn
        "accuracy": "accuracy",
    }
    # must pass explicitly — AG infers multiclass for integer labels (e.g. abalone Rings)
    if task == "regression":
        problem_type = "regression"
    elif y_train.nunique() == 2:
        problem_type = "binary"
    else:
        problem_type = "multiclass"

    _LABEL   = "__target__"
    train_df = X_train.copy()
    train_df[_LABEL] = y_train.values

    with tempfile.TemporaryDirectory() as tmp:
        pred = TabularPredictor(label=_LABEL, eval_metric=_METRIC.get(metric, metric),
                                problem_type=problem_type, path=tmp, verbosity=0)
        pred.fit(train_df, time_limit=time_budget)

        t0      = time.perf_counter()
        y_pred  = pred.predict(X_test).values
        y_proba = pred.predict_proba(X_test).values if task == "classification" else None
        infer_s = time.perf_counter() - t0

        board = pred.leaderboard(silent=True)
        best  = board.iloc[0]["model"] if not board.empty else "unknown"

    return y_pred, y_proba, infer_s, {"best_model": best, "best_config": {}}


def _run_h2o(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    import h2o
    from h2o.automl import H2OAutoML

    _METRIC = {"auc": "AUC", "log_loss": "logloss", "rmse": "RMSE", "accuracy": "mean_per_class_error"}
    _LABEL  = "__target__"

    h2o.init(verbose=False)

    train_df         = X_train.copy()
    train_df[_LABEL] = y_train.values
    train_h2o        = h2o.H2OFrame(train_df)
    test_h2o         = h2o.H2OFrame(X_test)

    if task == "classification":
        train_h2o[_LABEL] = train_h2o[_LABEL].asfactor()

    aml = H2OAutoML(max_runtime_secs=time_budget, sort_metric=_METRIC.get(metric, metric),
                    seed=42, verbosity=None)
    aml.train(y=_LABEL, training_frame=train_h2o)

    t0     = time.perf_counter()
    preds  = aml.leader.predict(test_h2o).as_data_frame()
    infer_s = time.perf_counter() - t0

    y_pred  = preds["predict"].values
    y_proba = preds.iloc[:, 1:].values if task == "classification" else None

    return y_pred, y_proba, infer_s, {"best_model": aml.leader.model_id, "best_config": {}}


def _run_lightautoml(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    from lightautoml.automl.presets.tabular_presets import TabularAutoML
    from lightautoml.tasks import Task

    _TASK = {"classification": "binary", "regression": "reg"}
    # lightautoml uses "multiclass" for >2 classes; detect from y
    lama_task = "multiclass" if task == "classification" and y_train.nunique() > 2 else _TASK[task]

    _LABEL   = "__target__"
    train_df = X_train.copy(); train_df[_LABEL] = y_train.values
    test_df  = X_test.copy()

    automl = TabularAutoML(task=Task(lama_task), timeout=time_budget)
    automl.fit_predict(train_df, roles={"target": _LABEL}, verbose=0)

    t0      = time.perf_counter()
    out     = automl.predict(test_df)
    infer_s = time.perf_counter() - t0

    if task == "classification":
        y_proba = out.data
        y_pred  = y_proba.argmax(axis=1) if y_proba.ndim > 1 else (y_proba[:, 0] > 0.5).astype(int)
    else:
        y_pred  = out.data.ravel()
        y_proba = None

    return y_pred, y_proba, infer_s, {"best_model": "lightautoml", "best_config": {}}


def _run_mljar(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    import tempfile
    from supervised.automl import AutoML

    _MODE = "Perform"   # Explain / Perform / Compete
    _ML_TASK = {
        ("classification", 2):  "binary_classification",
        ("classification", -1): "multiclass_classification",
        ("regression", -1):     "regression",
    }
    n_cls    = y_train.nunique() if task == "classification" else -1
    ml_task  = _ML_TASK.get((task, 2 if n_cls == 2 else -1), "regression")

    with tempfile.TemporaryDirectory() as tmp:
        automl = AutoML(mode=_MODE, total_time_limit=time_budget,
                        results_path=tmp, ml_task=ml_task, explain_level=0)
        automl.fit(X_train, y_train)

        t0      = time.perf_counter()
        y_pred  = automl.predict(X_test)
        y_proba = automl.predict_proba(X_test) if task == "classification" else None
        infer_s = time.perf_counter() - t0

        best = getattr(automl, "_best_model", {})
        best_name = best.get("name", "unknown") if isinstance(best, dict) else str(best)

    return y_pred, y_proba, infer_s, {"best_model": best_name, "best_config": {}}


def _run_dummy(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    from sklearn.dummy import DummyClassifier, DummyRegressor

    if task == "classification":
        model = DummyClassifier(strategy="most_frequent", random_state=42)
    else:
        model = DummyRegressor(strategy="mean")

    model.fit(X_train, y_train)

    t0      = time.perf_counter()
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test) if task == "classification" else None
    infer_s = time.perf_counter() - t0

    return y_pred, y_proba, infer_s, {"best_model": "dummy", "best_config": {}}


def _run_randomforest(X_train, y_train, X_test, task, metric, time_budget) -> tuple:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import RandomizedSearchCV

    param_dist = {
        "n_estimators": [100, 200, 500],
        "max_depth":    [None, 10, 20, 30],
        "max_features": ["sqrt", "log2", 0.5],
        "min_samples_leaf": [1, 2, 4],
    }
    _SCORING = {"auc": "roc_auc", "log_loss": "neg_log_loss",
                "rmse": "neg_root_mean_squared_error", "accuracy": "accuracy"}

    base  = RandomForestClassifier(random_state=42, n_jobs=-1) if task == "classification" \
            else RandomForestRegressor(random_state=42, n_jobs=-1)
    model = RandomizedSearchCV(base, param_dist, n_iter=20, cv=3,
                               scoring=_SCORING.get(metric, "accuracy"),
                               random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    t0      = time.perf_counter()
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test) if task == "classification" else None
    infer_s = time.perf_counter() - t0

    return y_pred, y_proba, infer_s, {
        "best_model":  "RandomForest",
        "best_config": model.best_params_,
    }


RUNNERS = {
    "flaml":        _run_flaml,
    "autogluon":    _run_autogluon,
    "h2o":          _run_h2o,
    "lightautoml":  _run_lightautoml,
    "mljar":        _run_mljar,
    "dummy":        _run_dummy,
    "randomforest": _run_randomforest,
}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework",   required=True, choices=list(RUNNERS))
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--fold",        required=True, type=int)
    parser.add_argument("--time-budget", required=True, type=int)
    parser.add_argument("--output",      required=True, help="Path to write result JSON")
    args = parser.parse_args()

    ds_dir    = Path(args.dataset_dir)
    meta      = json.loads((ds_dir / "meta.json").read_text())
    folds_doc = json.loads((ds_dir / "folds.json").read_text())

    label     = meta["label"]
    task      = meta["task"]
    metric    = meta.get("metric") or ("auc" if task == "classification" else "rmse")
    drop_cols = meta.get("drop_cols", [])

    df        = pd.read_csv(ds_dir / "train.csv")
    df        = df.drop(columns=[c for c in drop_cols if c in df.columns])
    X         = df.drop(columns=[label])
    y         = df[label]

    # auto-detect binary vs multiclass metric default
    if metric is None:
        metric = "auc" if y.nunique() == 2 else "accuracy"

    fold      = folds_doc["folds"][args.fold]
    X_train, y_train = X.iloc[fold["train"]], y.iloc[fold["train"]]
    X_test,  y_test  = X.iloc[fold["test"]],  y.iloc[fold["test"]]

    result = {
        "framework":   args.framework,
        "dataset":     ds_dir.name,
        "fold":        args.fold,
        "task":        task,
        "metric_name": metric,
        "label":       label,
        "status":      "failed",
        "error":       None,
        "failure_type": None,
        "framework_version": get_version(args.framework),
    }

    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        runner = RUNNERS[args.framework]
        y_pred, y_proba, infer_s, extra = runner(
            X_train, y_train, X_test, task, metric, args.time_budget
        )

        score = compute_score(y_test.values, y_pred, y_proba, metric)

        result.update({
            "status":           "done",
            "metric_score":     round(score, 6),
            "metric_score_raw": round(abs(score) if metric in ("rmse", "log_loss") else score, 6),
            "metric_direction": "lower_is_better" if metric in ("rmse", "log_loss") else "higher_is_better",
            "inference_time_s": round(infer_s, 4),
            **extra,
        })

    except MemoryError as e:
        result["error"] = str(e); result["failure_type"] = "oom"
    except TimeoutError as e:
        result["error"] = str(e); result["failure_type"] = "timeout"
    except Exception as e:
        result["error"] = str(e)
        msg = str(e).lower()
        result["failure_type"] = (
            "oom"     if "memory" in msg or "oom" in msg else
            "timeout" if "time"   in msg                  else
            "data"    if "nan" in msg or "dtype" in msg   else
            "impl"
        )

    duration = time.perf_counter() - t0
    _, peak  = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    result["resource_usage"] = {
        "duration_s":     round(duration, 2),
        "peak_memory_mb": round(peak / 1024 / 1024, 2),
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({"status": result["status"], "score": result.get("metric_score"),
                      "output": str(out)}))


if __name__ == "__main__":
    main()
