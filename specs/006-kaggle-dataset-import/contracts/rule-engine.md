# Contract — Adaptability Rule Engine (`storage/adapt.py`)

This is the heart of the feature and the answer to *"how do I add rules and keep Kaggle's breadth
tractable?"* You do not adapt to Kaggle. You declare the one shape the system accepts and let an
**ordered list of small, named rules** reject everything else with a reason.

## Types

```text
Verdict:
  ok: bool
  rule_id: str
  reason: str        # why it was rejected (empty when ok)
  hint: str          # optional: what the user can do about it
  Verdict.passed(rule_id) -> Verdict(ok=True, ...)
  Verdict.reject(rule_id, reason, hint="") -> Verdict(ok=False, ...)

Rule:
  id: str                      # stable, shown in the UI checklist (e.g. "R4-tabular-file")
  description: str             # one line
  phase: "pre" | "post"        # pre-download (metadata) | post-selection (bytes/sample)
  check: (Context) -> Verdict  # pure w.r.t. its inputs; reads ctx, returns a verdict
```

## Engine

```text
evaluate(rules: list[Rule], ctx: Context, phase: str) -> list[Verdict]
    # runs rules where rule.phase == phase, IN ORDER, stops at the first reject,
    # returns the verdicts gathered so far (passes + the one reject, or all passes)

all_ok(verdicts) -> bool        # True iff every verdict.ok
first_reject(verdicts) -> Verdict | None
```

**Fail-fast**: the first reject ends evaluation for that phase — the UI shows ✅ for every rule that
passed and ❌ on the one that failed (FR-010).

## The canonical rule set (v1, ordered)

Defined as a module-level list `RULES`. The engine never hard-codes rule logic — it only iterates.

### Pre-download phase (cheap; metadata only — no bytes transferred yet)

| id | description | rejects when | hint |
|---|---|---|---|
| `R1-url-shape` | URL is a public Kaggle **dataset** ref | not `kaggle.com/datasets/{owner}/{slug}` (competition `/c/…`, kernels, other hosts) | "v1 supports public Datasets only — not competitions or kernels." |
| `R2-credentials` | Kaggle API token is configured | `KAGGLE_USERNAME`/`KAGGLE_KEY` (or token file) absent | "A public link still needs a token. Set KAGGLE_USERNAME and KAGGLE_KEY." |
| `R3-reachable` | dataset exists & is listable | listing returns 403/404 or errors | "Check the dataset is public and the URL is correct." |
| `R4-tabular-file` | ≥1 tabular file (`.csv/.tsv/.parquet`) | zero tabular files (images/audio/text only) | "This dataset has no table — image/text datasets aren't supported." |
| `R5-size` | chosen/declared file ≤ cap | size > `KAGGLE_MAX_FILE_MB` (default 200) | "File is {actual}; limit is {cap} MB. Raise KAGGLE_MAX_FILE_MB to allow it." |

### Post-selection phase (after the user picks a file + target; needs a sample/bytes)

| id | description | rejects when | hint |
|---|---|---|---|
| `R6-parse-shape` | parses as a rectangular table, ≥2 columns, enough rows | unreadable / ragged / <2 columns / too few rows | "Couldn't read a table with a feature column + a target." |
| `R7-target-valid` | chosen target yields a supported task type | target is a per-row id or all-null and not a valid continuous regression target | "Pick a label column — this one looks like an identifier." |

> R6/R7 reuse `ingest.infer_metadata`, which already enforces "≥2 columns" and infers
> binary/multiclass/regression. R7 wraps it to **validate** an explicit target rather than only infer.

## How to add a rule (the extension recipe — SC-003)

Adding a constraint is a **one-unit change** in `storage/adapt.py`; the import flow (`ingest`) and the
UI (`datasets.py`) are untouched:

```text
1. Write a check:   def _check_max_columns(ctx) -> Verdict: ...
2. Append a Rule:   RULES.append(Rule("R8-max-columns", "≤2000 columns", "post", _check_max_columns))
3. Add one test in tests/test_kaggle_import.py asserting the new reject.
```

Because the engine iterates `RULES` and the UI renders whatever verdicts come back, no other code
changes. This is the property the spec requires (FR-009).

## Test contract

- Each rule has a unit test driving it to **reject** (and the happy path drives them all to pass).
- Tests construct a `Context` with a **fake client** (see `kaggle-client.md`) — no network.
- `evaluate` stops at first reject — a test asserts later rules are not run after a reject.
