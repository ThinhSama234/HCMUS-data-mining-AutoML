# Implementation Plan: Import a public Kaggle dataset by link

**Branch**: `006-kaggle-dataset-import` | **Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-kaggle-dataset-import/spec.md`

## Summary

Add a third dataset on-ramp to the console Datasets section: paste a **public Kaggle dataset URL**,
and the dataset lands in the catalog exactly like an uploaded CSV. Because Kaggle is unbounded in
shape, eligibility is decided by an **ordered, extensible rule pipeline** (the "adaptability
contract") that normalises a dataset into the one shape the system already consumes — a single
supervised tabular file with a chosen target — or **rejects it with a named, human-readable reason**.
Connection to Kaggle uses the official authenticated Kaggle API behind a thin, **mockable seam** so
tests stay hermetic. The existing object-store + `datasets`-row + `infer_metadata` ingestion path is
reused unchanged, so an imported Kaggle dataset is indistinguishable downstream.

## Technical Context

**Language/Version**: Python 3.9–3.11 (matches the CI test matrix and `requirements.txt`).

**Primary Dependencies**: Streamlit (UI), SQLAlchemy Core (catalog), pandas (table parsing),
boto3/MinIO (object store). **New**: `kaggle` (official Kaggle API client) — the only sanctioned way
to access Kaggle datasets programmatically.

**Storage**: Reused unchanged — object store via `storage/objectstore.py`; `datasets` table via
`storage/models.py` (Postgres in Docker / SQLite in dev+test). **No schema migration.**

**Testing**: pytest + Streamlit `AppTest`. The Kaggle access seam is replaced with a fake that serves
local fixture files, so the suite runs offline (the hermetic-test discipline established in CI).

**Target Platform**: The Streamlit console container (Linux) and local dev.

**Project Type**: Web application — a single Streamlit app with a storage layer. Single-project
structure.

**Performance Goals**: Interactive. Metadata/file-list fetch returns in a few seconds; one end-to-end
import of a known single-table dataset completes well under one minute (SC-001). Cheap rules run
**before** any download.

**Constraints**: Tests MUST NOT touch the network (FR-013); credentials live in environment only,
never the DB (FR-003); a configurable size cap protects the small VPS/object store (FR-006); existing
Upload-CSV and OpenML flows MUST keep working unchanged.

**Scale/Scope**: Single-user, one interactive import at a time (matches the console's current model).
No background queue, no new service.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution (`.specify/memory/constitution.md`) is the unfilled template — no ratified
principles. In their absence, this plan is checked against the **de-facto principles evident in the
codebase**, and passes each:

| De-facto principle (observed in code) | How this feature complies |
|---|---|
| **Hermetic, portable tests** (SQLite+PG schema via `with_variant`; Docker mocked in `test_console`) | Kaggle access is behind a mockable seam; all new tests use a fake client + local fixtures — zero network (FR-013, SC-004). |
| **Reuse the ingestion path** (`objectstore.put` + `_insert_dataset` + `infer_metadata` for both upload and OpenML) | Kaggle import reuses the same three; only the *acquisition* differs (FR-008, SC-005). |
| **Fail with a clear reason** (`ingest_upload` raises `ValueError` → UI toast) | Rules return structured verdicts surfaced in the UI; first failure stops the flow (FR-010, SC-002). |
| **Seam over external CLIs/services** (`integration._container_cli` abstracts docker/nerdctl/podman) | A `kaggle_client` seam abstracts the Kaggle API the same way, injectable for tests. |
| **No new daemon for single-user/local** (integration uses a detached one-off, not a server) | Import is synchronous within the Streamlit run; no server, no queue. |

**New dependency justification**: `kaggle` is added because Kaggle exposes no anonymous bulk
download; the official client is the standard, supported access path. This is recorded in Complexity
Tracking as a deliberate, minimal addition.

**Result**: PASS (no violations). Re-checked after Phase 1 — still PASS (design adds only a seam, a
rule module, two `ingest` functions, and a UI block; no new architecture).

## Project Structure

### Documentation (this feature)

```text
specs/006-kaggle-dataset-import/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature spec (what & why)
├── research.md          # Phase 0 — decisions: Kaggle access, rule phases, hermetic seam
├── data-model.md        # Phase 1 — Rule/Verdict/ImportSession + mapping to datasets row
├── quickstart.md        # Phase 1 — validate happy path + each rejection class, offline tests
├── contracts/
│   ├── rule-engine.md   # Rule interface, the canonical R1–R7, the "add a rule" recipe
│   ├── kaggle-client.md # The mockable access seam (parse/list/size/download)
│   └── ingest-and-ui.md # ingest.kaggle_* signatures + Datasets UI state-machine contract
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT this command)
```

### Source Code (repository root)

```text
storage/
├── kaggle_client.py     # NEW — thin seam over the official Kaggle API; get_client() factory
│                        #       (overridable in tests); parse_url, list_files, file_size, download_file
├── adapt.py             # NEW — Rule + Verdict types, the ordered RULES list, evaluate() engine
├── ingest.py            # EXTEND — kaggle_list(url) [pre-download rules] +
│                        #          kaggle_import(ref, file, target) [post-selection rules + store + row]
│                        #          reuses infer_metadata / objectstore.put / _insert_dataset
└── models.py            # UNCHANGED — datasets row reused; source="kaggle" (free-text column, no migration)

console/
└── views/
    └── datasets.py      # EXTEND — third ingest control + 3-state import session (st.session_state)
                         #          + rule-verdict checklist rendering

tests/
├── fixtures/
│   ├── kaggle_single/   # NEW — a one-CSV "dataset" for the happy path
│   ├── kaggle_multi/    # NEW — train.csv + test.csv + sample_submission.csv (US3)
│   └── kaggle_images/   # NEW — manifest with no tabular file (reject)
└── test_kaggle_import.py # NEW — rule-by-rule rejects + happy path + dedupe, all via the fake client

requirements.txt          # EXTEND — add `kaggle`
.env.example              # EXTEND — document KAGGLE_USERNAME / KAGGLE_KEY / KAGGLE_MAX_FILE_MB
docker-compose.yml        # EXTEND (optional) — pass the KAGGLE_* env into the console service
```

**Structure Decision**: Single project. The feature is a thin vertical slice — one acquisition seam
(`kaggle_client`), one rule module (`adapt`), two new `ingest` functions, and one UI block — sitting
on top of the unchanged datasets table and object store. The rule module is the only place that grows
when new constraints are added (SC-003).

## Complexity Tracking

> Only deviations from the simplest path are listed.

| Decision | Why needed | Simpler alternative rejected because |
|---|---|---|
| Add `kaggle` dependency | Kaggle has no anonymous bulk-download API; the official client is the supported path | Scraping the dataset page is fragile, breaks on markup changes, and violates Kaggle ToS |
| Rule **pipeline** (vs inline `if`s in `ingest`) | FR-009/SC-003: adding a rule must not touch the flow or UI; rules must be independently testable and self-describing | Inline checks couple every new constraint to the import function and UI, and can't render a per-rule checklist |
| Two rule **phases** (pre-download vs post-selection) | Don't download bytes until cheap metadata rules pass (perf + size-cap before transfer) | A single post-download phase wastes bandwidth/time on datasets that fail on URL shape or size |
| UI **state machine** (vs one-shot like Upload/OpenML) | Kaggle needs a fetch → pick file → pick target round-trip; Streamlit reruns require explicit session state | A one-shot control can't offer file/target selection for multi-file or unknown-schema datasets |
