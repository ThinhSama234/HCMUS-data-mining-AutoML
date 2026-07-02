# Quickstart — validate the Kaggle dataset import

A runnable validation guide once the feature is implemented. Proves US1 (happy path), US2 (every
rejection names its rule), and US3 (multi-file pick) — and that tests stay offline.

## Prerequisites

- The console running locally (`streamlit run console/app.py`) or via docker-compose.
- A Kaggle API token (only for the live happy path — **not** needed for the test suite):
  - Kaggle → Account → *Create New API Token* → downloads `kaggle.json`, OR
  - export `KAGGLE_USERNAME=<you>` and `KAGGLE_KEY=<key>`.
- Optional: `export KAGGLE_MAX_FILE_MB=200` (default).

## Scenario A — happy path (US1)

1. Open the **Datasets** section → *Add from Kaggle (public link)*.
2. Paste a known **single-table** public dataset URL, e.g.
   `https://www.kaggle.com/datasets/uciml/iris`.
3. Click **Fetch** → the rule checklist shows ✅ for R1–R5 and the file/target pickers appear.
4. Pick the target column → **Import**.
5. **Expected**: a success toast and a new row in the catalog with `source = kaggle`, a `task_type`,
   instance/feature counts, and a size tier — selectable in the training-run section (SC-005).
6. Re-import the same URL/file → **Expected**: it points to the existing entry, no duplicate (FR-012).

## Scenario B — every rejection names its rule (US2 / SC-002)

Each of these should stop with a **named** rule and a reason + hint — no stack trace:

| Input | Expected reject |
|---|---|
| A competition URL (`kaggle.com/competitions/titanic`) | `R1-url-shape` |
| Any URL with `KAGGLE_*` unset | `R2-credentials` ("a public link still needs a token") |
| A private / 404 / deleted dataset URL | `R3-reachable` |
| An image-only dataset | `R4-tabular-file` |
| A dataset whose table exceeds `KAGGLE_MAX_FILE_MB` | `R5-size` (states limit + actual) |
| A file whose chosen target is an id column | `R7-target-valid` |

## Scenario C — multi-file dataset (US3)

1. Fetch a dataset with `train.csv` + `test.csv` + `sample_submission.csv`.
2. **Expected**: a file picker lists the tabular files; nothing imports until one is chosen.
3. Choose `train.csv`, pick a target, **Import** → only that file is profiled and added.

## Offline test suite (SC-004 — the important one for CI)

No token, no network — the Kaggle seam is faked from local fixtures:

```bash
cd /path/to/automl-thesis
pytest -q tests/test_kaggle_import.py
```

**Expected**: all import + rejection cases pass with no network access (the suite injects a fake via
`kaggle_client.set_client(...)`), keeping CI green and fast — the same hermetic discipline that the
Tier-1 CI work established.

## Adding a new adaptability rule (SC-003)

To prove the extension property, add a rule and a test — touching only `storage/adapt.py` and the
test file (see [contracts/rule-engine.md](./contracts/rule-engine.md#how-to-add-a-rule-the-extension-recipe--sc-003)):

```text
1. def _check_max_columns(ctx): return Verdict.reject("R8-max-columns", ...) if ... else Verdict.passed("R8-max-columns")
2. RULES.append(Rule("R8-max-columns", "≤2000 columns", "post", _check_max_columns))
3. add a test asserting the reject
```

The import flow and the Datasets UI require **no changes** — confirming FR-009.

## References

- Behaviour & scope: [spec.md](./spec.md)
- Decisions: [research.md](./research.md)
- Types & state machine: [data-model.md](./data-model.md)
- Interfaces: [contracts/](./contracts/)
