"""Score-shaped views for the Evaluation page (report figures Hình 4/5/6/8).

Pure, UI-free helpers over the tidy results frame (`analysis.load_results` / `storage.repo.load`)
so the console and the report stay in sync (INV-2). One module groups the score-shaped figures
(KISS) instead of one file per chart:

- `normalized_scores` — per-dataset min-max normalized score in [0,1] (1 = best on that dataset),
  overall + by task type                                                        (Hình 4).
- `score_long`        — per-fold raw metric value per (dataset × framework), for boxplots (Hình 5).
- `score_vs_time`     — mean metric vs mean training time per (framework × dataset)  (Hình 6).
- `inference_times`   — per-fold inference (predict) time per framework            (Hình 8).

All are metric-safe: they never compare metrics across task types (FR-008); normalization and
grouping happen within a dataset / task type. Empty or column-missing input degrades to an empty
frame with the expected columns so the views can info-degrade like US3/US4.

CLI:  python -m analysis.score_shapes <results.csv>
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from analysis.load_results import load_results


def _successful(df):
    """Rows of completed runs (tolerates an object-dtype/absent `success` column)."""
    if df.empty or "success" not in df.columns:
        return df
    return df[df["success"].astype(bool)]


def _has_type(df):
    return "type" in df.columns


def normalized_scores(df):
    """Long df [framework, task, (type), norm_score] — score min-max normalized within each task.

    On each task the best framework scores 1.0 and the worst 0.0 (all-equal → 1.0). Uses the
    higher-is-better `score`, so normalization is metric-agnostic and comparable across datasets.
    """
    cols = ["framework", "task"] + (["type"] if _has_type(df) else []) + ["norm_score"]
    ok = _successful(df)
    ok = ok[ok["score"].notna()] if "score" in ok.columns else ok.iloc[0:0]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    if _has_type(ok):  # keep NULL-type datasets as 'unknown' (don't silently drop, cf. score_long)
        ok = ok.assign(type=ok["type"].fillna("unknown"))
    keys = ["task", "framework"] + (["type"] if _has_type(ok) else [])
    m = ok.groupby(keys, as_index=False)["score"].mean()
    lo = m.groupby("task")["score"].transform("min")
    hi = m.groupby("task")["score"].transform("max")
    span = hi - lo
    m["norm_score"] = np.where(span > 0, (m["score"] - lo) / span.replace(0, np.nan), 1.0)
    return m[cols].reset_index(drop=True)


def score_long(df):
    """Per-fold raw metric value per (dataset × framework): [task, (type), framework, fold, metric_value].

    `metric_value` is the raw `result_num` (the same column the per-task table shows; higher-is-better
    only when the source pre-orients it, e.g. AMLB neg_rmse). Grouped per dataset downstream, so
    metric sign/scale never mixes across task types.
    """
    base = [c for c in ["task", "type", "framework", "fold"] if c in df.columns]
    cols = base + ["metric_value"]
    ok = _successful(df)
    ok = ok[ok["result_num"].notna()] if "result_num" in ok.columns else ok.iloc[0:0]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    out = ok[base + ["result_num"]].rename(columns={"result_num": "metric_value"})
    if "type" in out.columns:  # consistent with normalized_scores/score_vs_time: unknown, not dropped
        out = out.assign(type=out["type"].fillna("unknown"))
    return out.reset_index(drop=True)


def score_vs_time(df):
    """Mean metric vs mean training time per (framework × dataset): [framework, task, (type), mean_score, mean_train_s]."""
    cols = ["framework", "task"] + (["type"] if _has_type(df) else []) + ["mean_score", "mean_train_s"]
    ok = _successful(df)
    need = {"result_num", "training_duration"}
    if ok.empty or not need.issubset(ok.columns):
        return pd.DataFrame(columns=cols)
    ok = ok[ok["result_num"].notna() & ok["training_duration"].notna()]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    if _has_type(ok):  # keep NULL-type datasets as 'unknown' (consistent across the score figures)
        ok = ok.assign(type=ok["type"].fillna("unknown"))
    keys = ["framework", "task"] + (["type"] if _has_type(ok) else [])
    g = ok.groupby(keys, as_index=False).agg(mean_score=("result_num", "mean"),
                                             mean_train_s=("training_duration", "mean"))
    return g[cols].reset_index(drop=True)


def inference_times(df):
    """Per-fold inference time per framework: [framework, predict_s]. Empty if predict_duration absent."""
    cols = ["framework", "predict_s"]
    ok = _successful(df)
    if ok.empty or "predict_duration" not in ok.columns:
        return pd.DataFrame(columns=cols)
    ok = ok[ok["predict_duration"].notna()]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    return (ok[["framework", "predict_duration"]]
            .rename(columns={"predict_duration": "predict_s"}).reset_index(drop=True))


def budget_performance(df):
    """Normalized performance per (framework × time budget): [framework, constraint, mean_norm] (Hình 7).

    Score is min-max normalized within each dataset across all (framework, budget) cells, then
    averaged per (framework, constraint) — so a framework that improves with a bigger budget rises.
    Needs a `constraint` column; a single budget yields one bar per framework (the view notes it).
    """
    cols = ["framework", "constraint", "mean_norm"]
    ok = _successful(df)
    if ok.empty or "constraint" not in ok.columns or "score" not in ok.columns:
        return pd.DataFrame(columns=cols)
    ok = ok[ok["score"].notna() & ok["constraint"].notna()]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    m = ok.groupby(["task", "framework", "constraint"], as_index=False)["score"].mean()
    lo = m.groupby("task")["score"].transform("min")
    hi = m.groupby("task")["score"].transform("max")
    span = hi - lo
    m["norm"] = np.where(span > 0, (m["score"] - lo) / span.replace(0, np.nan), 1.0)
    g = (m.groupby(["framework", "constraint"], as_index=False)["norm"].mean()
         .rename(columns={"norm": "mean_norm"}))
    return g[cols].reset_index(drop=True)


def budget_usage(df):
    """Allocated-vs-actual time per framework: [framework, (constraint), mean_train_s, budget_s, pct_used].

    ``budget_s`` is the constraint's allocated ``max_runtime_seconds`` (equal for every framework in a
    run → fairness); ``pct_used`` is how much of it the framework's mean training actually consumed.
    Empty when the budget/duration columns are absent (e.g. CSV-only data without a constraint).
    """
    cols = ["framework", "constraint", "mean_train_s", "budget_s", "pct_used"]
    ok = _successful(df)
    if ok.empty or not {"training_duration", "budget_s"}.issubset(ok.columns):
        return pd.DataFrame(columns=cols)
    ok = ok[ok["training_duration"].notna() & ok["budget_s"].notna() & (ok["budget_s"] > 0)]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    keys = ["framework"] + (["constraint"] if "constraint" in ok.columns else [])
    g = ok.groupby(keys, as_index=False).agg(mean_train_s=("training_duration", "mean"),
                                             budget_s=("budget_s", "median"))
    g["pct_used"] = (100 * g["mean_train_s"] / g["budget_s"]).round(1)
    return g[[c for c in cols if c in g.columns]].reset_index(drop=True)


def main(argv):
    if len(argv) < 2:
        print("usage: python -m analysis.score_shapes <results.csv>", file=sys.stderr)
        return 2
    df = load_results(argv[1])
    print("# Normalized score (1 = best on the dataset)\n")
    print(normalized_scores(df).to_string(index=False))
    print("\n# Score vs training time\n")
    print(score_vs_time(df).to_string(index=False))
    inf = inference_times(df)
    print(f"\n# Inference time: {len(inf)} rows"
          + ("" if inf.empty else f", median {inf['predict_s'].median():.3f}s"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
