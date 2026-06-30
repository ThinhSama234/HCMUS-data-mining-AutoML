---
description: "Task list for 006-kaggle-dataset-import"
---

# Tasks: Import a public Kaggle dataset by link

**Input**: Design documents from `/specs/006-kaggle-dataset-import/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the spec explicitly requires hermetic, offline verifiability (FR-013, SC-004)
and the contracts define a test matrix. All tests inject a fake Kaggle client; none touch the network.

**Organization**: Grouped by user story so each is implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different file, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (user-story phases only)

## Path Conventions

Single project (Python web app). Code at repo root: `storage/`, `console/`, `tests/`. Paths below
are relative to the `automl-thesis` repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Declare the new dependency and configuration; no behaviour yet.

- [X] T001 [P] Add `kaggle` (official API client) to `requirements.txt`
- [X] T002 [P] Document `KAGGLE_USERNAME`, `KAGGLE_KEY`, and `KAGGLE_MAX_FILE_MB` (default 200) in `.env.example`
- [X] T003 [P] Extend the `source` column comment in `storage/models.py` to list `kaggle` (advisory only — no schema migration)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The mockable seam + the rule engine + the hermetic test harness. Every user story
depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create the Kaggle access seam in `storage/kaggle_client.py`: a `Ref` value object (`owner`, `slug`, `.path`, `.canonical_url`), and methods `parse_url`, `list_files`, `file_size`, `download_file` (single-file fetch + bounded zip extraction with a size guard), `credentials_present()`, a lazy `get_client()` / `set_client()` factory (the real `kaggle` import happens **inside** the factory, never at module import), and a `KaggleAccessError`. Per [contracts/kaggle-client.md](./contracts/kaggle-client.md).
- [X] T005 [P] Create the rule engine in `storage/adapt.py`: `Verdict` (`passed` / `reject` constructors), `Rule` (`id`, `description`, `phase`, `check`), a `Context` dataclass, `evaluate(rules, ctx, phase)` (ordered, **fail-fast** at first reject), `all_ok`, `first_reject`, and an (initially empty) module-level `RULES` list. Per [contracts/rule-engine.md](./contracts/rule-engine.md).
- [X] T006 Create the hermetic test harness in `tests/test_kaggle_import.py` and fixtures: a `FakeKaggleClient` implementing the seam interface, fixture dirs `tests/fixtures/kaggle_single/` (one `data.csv`), `tests/fixtures/kaggle_multi/` (`train.csv` + `test.csv` + `sample_submission.csv`), `tests/fixtures/kaggle_images/` (manifest with `.jpg` only, no table), plus the shared setup (temp SQLite via `DATABASE_URL` + `db._engine=None`, and `kaggle_client.set_client(fake)`). Depends on T004, T005.

**Checkpoint**: seam + engine + fake/fixtures ready — user stories can begin.

---

## Phase 3: User Story 1 - Import a single-table public Kaggle dataset by link (Priority: P1) 🎯 MVP

**Goal**: Paste a public Kaggle dataset URL that has one tabular file, pick the target column, and it
lands in the catalog like an uploaded CSV (stored, profiled, selectable for training).

**Independent Test**: With the fake client serving `kaggle_single/`, run `kaggle_list(url)` →
`kaggle_import(ref, file, target)` and assert a `datasets` row exists with `source="kaggle"` and a
correct `task_type`; re-import the same file and assert the same `dataset_id` is returned (dedupe).
No network.

### Tests for User Story 1 ⚠️ (write first; expect failure until implemented)

- [X] T007 [P] [US1] In `tests/test_kaggle_import.py`: happy-path single-table import (assert `datasets` row with `source="kaggle"` + inferred `task_type`/counts), dedupe (second import of the same file returns the same `dataset_id`, `deduped=True`), and an `AppTest` smoke test that the Datasets page boots with the Kaggle control and no exception.

### Implementation for User Story 1

- [X] T008 [P] [US1] Implement the pass-path rules in `storage/adapt.py` and register them in `RULES`: `R1-url-shape`, `R2-credentials`, `R4-tabular-file` (single-file selection), `R6-parse-shape`, `R7-target-valid`. (`R6`/`R7` reuse `ingest.infer_metadata`.)
- [X] T009 [US1] Implement `kaggle_list(url)` in `storage/ingest.py`: build a `Context` (`url`, `client=get_client()`, `max_file_mb` from env), run the PRE-download rules, and return `{ref, files, verdicts, ok}`.
- [X] T010 [US1] Implement `kaggle_import(ref, file_name, target_column)` in `storage/ingest.py`: download the chosen file via the seam (≤ cap), read with pandas, run POST rules (R6/R7), dedupe by `checksum_sha256`, else `objectstore.put("datasets", …)` + `_insert_dataset(source="kaggle", file_format="csv", …, **infer_metadata(df, target_column))`; return an `ImportResult`. (Depends on T009.)
- [X] T011 [US1] Add the "Add from Kaggle (public link)" control to `console/views/datasets.py`: a URL input + **Fetch** button and the 3-state session machine (`idle → fetched → ready`) for the **single-file** path — target-column picker (from a header/sample read), **Import** button, success `st.toast`, and **Reset**. (Depends on T009, T010.)

**Checkpoint**: a clean single-table public Kaggle dataset imports end-to-end — MVP is demoable.

---

## Phase 4: User Story 2 - See exactly why a dataset is or isn't adaptable (Priority: P2)

**Goal**: Every unsupported input is rejected with the **named** failed rule + reason + hint, shown as
a ✅/❌ checklist; the pipeline stops at the first reject.

**Independent Test**: Feed each reject class via the fake client/params and assert a distinct, named
verdict; assert `evaluate` does not run rules after the first reject.

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] In `tests/test_kaggle_import.py`: one rejection test per rule — `R1` (competition URL), `R2` (creds absent), `R3` (private/404 → `KaggleAccessError`), `R4` (images-only fixture), `R5` (oversized `FileInfo`), `R7` (id-like target) — plus a test asserting `evaluate` stops at the first reject (later rules not invoked).

### Implementation for User Story 2

- [X] T013 [P] [US2] Implement the reject-focused rules in `storage/adapt.py` and register in `RULES`: `R3-reachable` (turn `KaggleAccessError` into a reject) and `R5-size` (reject when size > `KAGGLE_MAX_FILE_MB`, stating both the limit and the actual size).
- [X] T014 [P] [US2] Render the verdict checklist in `console/views/datasets.py`: for each `Verdict` show ✅/❌ + `rule_id` + reason and a `💡 hint` on rejects; highlight the first reject; wire it into both the `fetched` and reject states. (Depends on T011.)

**Checkpoint**: US1 still works; every rejection is now explained in the UI.

---

## Phase 5: User Story 3 - Choose which file to import from a multi-file dataset (Priority: P3)

**Goal**: When a dataset bundles several tabular files, the user picks which one becomes the dataset.

**Independent Test**: With the fake client serving `kaggle_multi/`, `kaggle_list` returns >1 file and
no auto-import happens; importing a chosen file profiles only that file.

### Tests for User Story 3 ⚠️

- [X] T015 [P] [US3] In `tests/test_kaggle_import.py`: multi-file fixture → `kaggle_list` returns multiple tabular candidates; importing a chosen file (e.g. `train.csv`) profiles only that file and creates one catalog row.

### Implementation for User Story 3

- [X] T016 [P] [US3] Adjust `R4-tabular-file` in `storage/adapt.py` and `kaggle_list` in `storage/ingest.py` so that when >1 tabular file exists, all candidates are returned and no file is auto-selected (single-file behaviour from US1 unchanged).
- [X] T017 [P] [US3] Add the file-picker step to the `fetched` state in `console/views/datasets.py`: a selectbox of tabular files shown only when >1 exists; block **Import** until one is chosen. (Depends on T011.)

**Checkpoint**: all three stories work independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T018 [P] Pass `KAGGLE_USERNAME`, `KAGGLE_KEY`, `KAGGLE_MAX_FILE_MB` into the `console` service environment in `docker-compose.yml`
- [X] T019 [P] Add an "Add from Kaggle" note to the README/console docs: credentials setup + the supported single-table-shape boundary (link to [quickstart.md](./quickstart.md))
- [X] T020 Run `pytest -q` — confirm the suite is green and the existing Upload/OpenML + Datasets `AppTest` tests are unaffected (SC-004/SC-005); then walk [quickstart.md](./quickstart.md) scenarios A–C

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: after Setup — **blocks all stories**. (T004, T005 parallel; T006 after both.)
- **User stories (P3–P5)**: each starts after Foundational. US1 is the MVP and fully independent.
  US2 and US3 layer onto US1's UI (`datasets.py`) but are independently *testable* via their own tests.
- **Polish (P6)**: after the desired stories.

### Story dependency notes

- **US1 (P1)**: depends only on Foundational.
- **US2 (P2)**: rules (T013) depend only on the engine; the checklist (T014) extends US1's control (T011).
- **US3 (P3)**: the picker (T017) extends US1's control (T011); list logic (T016) extends T008/T009.

### Within a story

- The same file is never edited by two parallel tasks. `storage/ingest.py` tasks (T009, T010) are
  sequential; `console/views/datasets.py` is touched by T011 → T014 → T017 across phases (sequential).

---

## Parallel Example

```bash
# Setup — all three at once:
T001 Add `kaggle` to requirements.txt
T002 Document KAGGLE_* in .env.example
T003 Update source comment in storage/models.py

# Foundational — the seam and the engine are independent files:
T004 storage/kaggle_client.py
T005 storage/adapt.py

# User Story 1 — write the test while implementing the rules (different files):
T007 tests/test_kaggle_import.py   (happy path + dedupe + AppTest)
T008 storage/adapt.py              (pass-path rules R1,R2,R4,R6,R7)
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** the happy path +
dedupe offline (quickstart Scenario A) → demo. This alone is a usable new dataset on-ramp.

### Incremental delivery

- MVP (US1) → add US2 (transparent rejects, quickstart Scenario B) → add US3 (multi-file picker,
  quickstart Scenario C). Each increment adds value without breaking the previous.

### Notes

- `[P]` = different file, no incomplete-task dependency.
- All new tests are hermetic (fake client + temp SQLite) — never hit Kaggle.
- Adding a future rule = one new `Rule` in `storage/adapt.py` + one test; the flow and UI don't change.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

## Task summary

- **Total**: 20 tasks (T001–T020).
- **Per story**: Setup 3 · Foundational 3 · US1 5 · US2 3 · US3 3 · Polish 3.
- **MVP scope**: T001–T011 (Setup + Foundational + US1).
- **Tests**: included (hermetic) — 1 test task per story (T007, T012, T015) plus the T006 harness.
