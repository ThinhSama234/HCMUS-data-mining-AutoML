# Phase 1 — Data Model

This feature adds **no database tables and no migration**. It introduces small in-memory types (the
rule engine + import session) and reuses the existing `datasets` row. Below: the new types, the UI
state machine, and the mapping into the catalog.

## New in-memory types (`storage/adapt.py`)

### `Verdict`
The outcome of one rule.

| Field | Type | Notes |
|---|---|---|
| `ok` | bool | True = pass, False = reject |
| `rule_id` | str | e.g. `"R1-url-shape"` — stable id shown in the UI checklist |
| `reason` | str | Human-readable; empty when `ok` |
| `hint` | str | Optional remediation ("v1 supports public Datasets only") |

Constructors: `Verdict.passed(rule_id)` and `Verdict.reject(rule_id, reason, hint="")`.

### `Rule`
A named, ordered eligibility check.

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable identifier |
| `description` | str | One line, shown in the checklist |
| `phase` | `"pre"` \| `"post"` | pre-download (metadata) vs post-selection (bytes/sample) |
| `check` | `(Context) -> Verdict` | Pure function of the context; no I/O of its own beyond the seam |

The **engine**: `evaluate(rules, context) -> list[Verdict]` runs rules of the active phase in order,
**stops at the first reject**, and returns the verdicts gathered so far (so the UI can show ✅ up to
the ❌). `all_ok(verdicts) -> bool` is a convenience.

### `Context`
The bag a rule reads from (built incrementally across phases). Fields are optional until their phase.

| Field | Set by | Used by |
|---|---|---|
| `url` | user input | R1 |
| `ref` (`owner`, `slug`) | R1 parse | R3, R4, dedupe |
| `client` | `get_client()` | R2, R3, R4 |
| `files` (name, size_bytes) | R3/R4 listing | R4, R5 |
| `chosen_file` | user pick (US3) | R5, R6 |
| `sample_df` | header/sample read | R6, R7 |
| `target_column` | user pick | R7 |
| `max_file_mb` | env | R5 |

## Import session (UI state — `st.session_state`)

The Kaggle import is multi-step, so the Datasets view holds a small state machine. (Upload/OpenML are
one-shot and need none of this.)

```text
        paste URL + Fetch                pick file (if >1) + target            Import
 IDLE ───────────────────────▶ FETCHED ───────────────────────────────▶ READY ─────────▶ (toast) ─▶ IDLE
   ▲    run PRE rules (R1–R5)     │        run POST rules (R6–R7)          │   store + row
   │    reject ─────────────────────────────────────────────────────────────────────────┐
   └──────────────────────────── show verdict checklist; "Reset" ────────────────────────┘
```

Session keys (namespaced `kg_*` to avoid collisions):

| Key | Type | Meaning |
|---|---|---|
| `kg_state` | `"idle"`\|`"fetched"`\|`"ready"` | current step |
| `kg_ref` | dict | parsed `{owner, slug}` |
| `kg_files` | list | tabular candidates `[{name, size_bytes}]` |
| `kg_file` | str | chosen file name |
| `kg_columns` | list[str] | columns from the sample read |
| `kg_verdicts` | list[Verdict] | last evaluation, for rendering |

Transitions are guarded by `all_ok`: a reject anywhere keeps the state and renders the checklist with
the failed rule highlighted.

## Reused entity: `datasets` row (no change)

A Kaggle import writes one `datasets` row via the existing `_insert_dataset`. Column population:

| Column | Value on Kaggle import |
|---|---|
| `name` | `"kaggle:{owner}/{slug}/{file}"` (deduped against the `name` unique-constraint) |
| `source` | `"kaggle"` *(free-text column; update the advisory comment to list it)* |
| `file_format` | `"csv"` |
| `storage_uri` | object-store key from `objectstore.put("datasets", …)` |
| `checksum_sha256` | SHA-256 of the file bytes — **dedupe key** |
| `status` | `"ready"` |
| `task_type`, `target_column`, `n_instances`, `n_features`, `n_classes`, `minority_fraction`, `size_tier` | from `infer_metadata(df, target_column=<user pick>)` |
| `openml_task_id` | NULL |

**Dedupe**: before insert, look up an existing row by `checksum_sha256` (and/or the derived `name`); if
found, return that `dataset_id` (mirrors the OpenML `openml_task_id` de-dupe).

## Validation rules (summary; full text in `contracts/rule-engine.md`)

| Phase | Rule | Rejects when |
|---|---|---|
| pre | R1 url-shape | not a `kaggle.com/datasets/{owner}/{slug}` URL |
| pre | R2 credentials | no Kaggle token configured |
| pre | R3 reachable | dataset private/404/listing fails |
| pre | R4 tabular-file | zero tabular files (image/text-only) |
| pre | R5 size | chosen/declared file > `KAGGLE_MAX_FILE_MB` |
| post | R6 parse-shape | not a rectangular table with ≥2 columns / too few rows |
| post | R7 target-valid | target is per-row id or all-null and not a valid regression target |
