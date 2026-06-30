"""Adaptability rules (spec 006) — the ordered contract deciding if a Kaggle dataset is importable.

Don't adapt to all of Kaggle: define one target shape — a single tabular file plus a chosen target
column, which is exactly what `ingest.infer_metadata` and the `datasets` catalog already consume —
then gate every import through this ORDERED list of rules. Each rule reads the Context and returns a
Verdict (pass / reject + a human-readable reason + a hint); the engine runs them fail-fast.

Adding a constraint = append one Rule to RULES (+ a test). The ingest flow and the UI never change
(FR-009). Rules are pure functions of the Context; all network/IO is done by storage/ingest.py before
each phase and handed in via the Context, which keeps rules trivially unit-testable.

Phases (the order in which the data becomes available):
  url    R1, R2     — from the URL + env, before any network
  list   R3, R4, R5 — after listing the dataset's files (metadata only, no download)
  shape  R6         — after the chosen file is downloaded + parsed
  target R7         — after the user picks the target column
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

TABULAR_EXTS = (".csv", ".tsv", ".parquet")
MIN_ROWS = 10


@dataclass
class Verdict:
    ok: bool
    rule_id: str
    reason: str = ""
    hint: str = ""

    @staticmethod
    def passed(rule_id: str) -> "Verdict":
        return Verdict(True, rule_id)

    @staticmethod
    def reject(rule_id: str, reason: str, hint: str = "") -> "Verdict":
        return Verdict(False, rule_id, reason, hint)


@dataclass
class Context:
    """The bag a rule reads from, filled incrementally by ingest across phases."""
    url: str = ""
    ref: object = None                      # kaggle_client.Ref | None
    creds: bool = False
    files: Optional[list] = None            # list[FileInfo] | None
    list_error: Optional[str] = None
    max_file_mb: int = 200
    file_name: str = ""
    df: Optional[pd.DataFrame] = None
    parse_error: Optional[str] = None
    target_column: str = ""


@dataclass
class Rule:
    id: str
    description: str
    phase: str
    check: Callable[[Context], Verdict]


def _tabular(files):
    return [f for f in (files or []) if str(getattr(f, "name", "")).lower().endswith(TABULAR_EXTS)]


def _r1_url_shape(ctx: Context) -> Verdict:
    if ctx.ref is None:
        return Verdict.reject(
            "R1-url-shape",
            "not a Kaggle dataset URL (expected kaggle.com/datasets/{owner}/{slug})",
            "v1 supports public Datasets only — not competitions or kernels")
    return Verdict.passed("R1-url-shape")


def _r2_credentials(ctx: Context) -> Verdict:
    if not ctx.creds:
        return Verdict.reject(
            "R2-credentials",
            "no Kaggle API token configured",
            "set KAGGLE_USERNAME and KAGGLE_KEY — a public link still needs a token")
    return Verdict.passed("R2-credentials")


def _r3_reachable(ctx: Context) -> Verdict:
    if ctx.list_error:
        return Verdict.reject("R3-reachable", f"could not list the dataset: {ctx.list_error}",
                              "check the URL and that the dataset is public")
    if ctx.files is None:
        return Verdict.reject("R3-reachable", "dataset file listing is unavailable",
                              "check the URL and that the dataset is public")
    return Verdict.passed("R3-reachable")


def _r4_tabular_file(ctx: Context) -> Verdict:
    if not _tabular(ctx.files):
        return Verdict.reject(
            "R4-tabular-file",
            "no tabular file (.csv / .tsv / .parquet) in this dataset",
            "this connector imports tables only — image/audio/text datasets are unsupported")
    return Verdict.passed("R4-tabular-file")


def _r5_size(ctx: Context) -> Verdict:
    cap = ctx.max_file_mb * 1024 * 1024
    sized = [f.size_bytes for f in _tabular(ctx.files) if f.size_bytes is not None]
    if sized and all(s > cap for s in sized):
        return Verdict.reject(
            "R5-size",
            f"smallest tabular file is {min(sized) / 1e6:.0f} MB; limit is {ctx.max_file_mb} MB",
            "raise KAGGLE_MAX_FILE_MB to allow larger files")
    return Verdict.passed("R5-size")


def _r6_parse_shape(ctx: Context) -> Verdict:
    if ctx.parse_error:
        return Verdict.reject("R6-parse-shape", f"could not read a table: {ctx.parse_error}",
                              "needs a readable delimited or columnar table")
    df = ctx.df
    if df is None or df.shape[1] < 2:
        return Verdict.reject("R6-parse-shape", "table needs at least 2 columns (features + target)",
                              "this file has fewer than 2 columns")
    if len(df) < MIN_ROWS:
        return Verdict.reject("R6-parse-shape", f"only {len(df)} rows; need at least {MIN_ROWS}",
                              "too few rows to profile a task")
    return Verdict.passed("R6-parse-shape")


def _r7_target_valid(ctx: Context) -> Verdict:
    df, target = ctx.df, ctx.target_column
    if df is None or target not in list(getattr(df, "columns", [])):
        return Verdict.reject("R7-target-valid", "no target column selected", "pick a target column")
    y = df[target]
    if y.isna().all():
        return Verdict.reject("R7-target-valid", f"target '{target}' is entirely empty",
                              "pick a populated column")
    n_unique = int(y.nunique(dropna=True))
    if n_unique < 2:
        return Verdict.reject("R7-target-valid", f"target '{target}' has a single value",
                              "pick a column with at least 2 distinct values")
    # an all-unique non-numeric column is an identifier, not a label
    # (a numeric all-unique column is a valid continuous regression target)
    if not pd.api.types.is_numeric_dtype(y) and n_unique / len(df) > 0.9:
        return Verdict.reject("R7-target-valid",
                              f"target '{target}' looks like an identifier (mostly-unique text)",
                              "pick a real label column")
    return Verdict.passed("R7-target-valid")


RULES = [
    Rule("R1-url-shape", "URL is a public Kaggle dataset", "url", _r1_url_shape),
    Rule("R2-credentials", "Kaggle API token configured", "url", _r2_credentials),
    Rule("R3-reachable", "dataset exists and is listable", "list", _r3_reachable),
    Rule("R4-tabular-file", "has at least one tabular file", "list", _r4_tabular_file),
    Rule("R5-size", "a tabular file fits the size cap", "list", _r5_size),
    Rule("R6-parse-shape", "parses as a table with >= 2 columns", "shape", _r6_parse_shape),
    Rule("R7-target-valid", "chosen target yields a task type", "target", _r7_target_valid),
]


def evaluate(ctx: Context, phases) -> list:
    """Run RULES whose phase is in `phases`, in order, stopping at the first reject (fail-fast)."""
    out = []
    for rule in RULES:
        if rule.phase not in phases:
            continue
        verdict = rule.check(ctx)
        out.append(verdict)
        if not verdict.ok:
            break
    return out


def all_ok(verdicts) -> bool:
    return all(v.ok for v in verdicts)


def first_reject(verdicts):
    return next((v for v in verdicts if not v.ok), None)
