# Contract — Ingest functions + Datasets UI state machine

## `storage/ingest.py` — two new functions

These wrap the rule engine + the seam and reuse the existing `infer_metadata` / `objectstore.put` /
`_insert_dataset`. They contain **no rule logic** (that lives in `adapt.py`) and **no Kaggle imports**
(that lives in `kaggle_client.py`).

```text
kaggle_list(url: str) -> KaggleListing
    # builds Context(url, client=get_client(), max_file_mb=env)
    # runs the PRE-download rules (R1–R5 minus the file-specific size check when >1 file)
    # returns KaggleListing:
    #   { ref: Ref, files: [FileInfo], verdicts: [Verdict], ok: bool }
    # ok=False → caller shows the verdict checklist; no download happened

kaggle_import(ref: Ref, file_name: str, target_column: str) -> ImportResult
    # downloads the chosen file via the seam (≤ cap), reads it with pandas,
    # runs the POST-selection rules (R5 exact size, R6 parse-shape, R7 target-valid),
    # on full pass: dedupe by checksum → else objectstore.put + _insert_dataset(source="kaggle", …)
    # returns ImportResult:
    #   { ok: bool, dataset_id: int | None, deduped: bool, verdicts: [Verdict], error: str | None }
```

Both return **structured results** (never raise for an *unsupported* dataset — that's a verdict). They
may raise only for truly transient faults (network), which the UI shows as a retryable error.

### Reuse (unchanged) — mirrors `ingest_upload` / `ingest_openml`

- `infer_metadata(df, target_column=<user pick>)` — already supports an explicit target.
- `objectstore.put("datasets", "<uuid>.csv", data)` → `storage_uri`.
- `_insert_dataset(eng, name=…, source="kaggle", file_format="csv", storage_uri=…,
  checksum_sha256=…, status="ready", **meta)`.
- Dedupe pattern copied from `ingest_openml` (which checks `openml_task_id` first); here the key is
  `checksum_sha256`.

## `console/views/datasets.py` — third ingest control

A third column/expander beside **Upload CSV** and **Add from OpenML**: *"Add from Kaggle (public
link)"*. It runs a 3-state session machine (keys namespaced `kg_*`, see data-model.md).

### State contract

| State | Renders | Action → next |
|---|---|---|
| `idle` | URL text input + **Fetch** button | Fetch → `kaggle_list(url)`; if `ok` → store ref/files → `fetched`; else stay, show verdicts |
| `fetched` | rule checklist (✅/❌); **file picker** if >1 tabular file; **target picker** (from sample columns); **Import** + **Reset** | Import → `kaggle_import(ref, file, target)`; if `ok` → toast + `idle` + catalog refresh; else show verdicts |
| (any reject) | the verdict checklist with the failed rule highlighted (reason + hint) | **Reset** → `idle` |

### Rendering the verdict checklist (FR-010, SC-002)

```text
for v in verdicts:
    icon = "✅" if v.ok else "❌"
    st.write(f"{icon} {v.rule_id} — {v.reason or 'ok'}")
    if not v.ok and v.hint:
        st.caption(f"💡 {v.hint}")
```

### Existing behaviour preserved

- Upload-CSV and OpenML controls are unchanged.
- The catalog table below (`repo.list_datasets()` + presigned download links) is unchanged; the new
  Kaggle row appears there automatically after a successful import.

## Test contract (`tests/test_kaggle_import.py`, hermetic)

| Test | Asserts |
|---|---|
| happy path (single) | `kaggle_list` ok → `kaggle_import` ok → a `datasets` row with `source="kaggle"`, correct `task_type` |
| competition URL | `kaggle_list` → reject `R1-url-shape` |
| no credentials | reject `R2-credentials` (fake reports creds absent) |
| private/404 | reject `R3-reachable` (fake raises `KaggleAccessError`) |
| images-only | reject `R4-tabular-file` |
| oversized | reject `R5-size` with the limit in the reason |
| bad target (id col) | `kaggle_import` → reject `R7-target-valid` |
| multi-file | `kaggle_list` returns >1 file; importing a chosen file profiles only that file |
| dedupe | importing the same file twice → second returns the same `dataset_id`, `deduped=True` |
| AppTest render | the Datasets page boots and the Kaggle control renders with no exception |

All tests inject a fake via `kaggle_client.set_client(...)` and a temp SQLite (`DATABASE_URL` +
`db._engine=None`), per the established hermetic pattern in `tests/test_storage.py` /
`tests/test_console.py`.
