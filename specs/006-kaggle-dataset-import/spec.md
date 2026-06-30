# Feature Specification: Import a public Kaggle dataset by link

**Feature Branch**: `006-kaggle-dataset-import`

**Created**: 2026-06-30

**Status**: Draft

**Input**: User description: "Code the UI to import a dataset from a public Kaggle link. How do I add rules and connect to public Kaggle and constrain it — Kaggle feels too broad to adapt to all of it."

## Context & framing

Kaggle hosts almost every shape of data: multi-file dumps, image/audio/text corpora, nested
archives, SQLite dumps, and tabular files with arbitrary schemas — from a few KB to many GB.
The AutoML console consumes exactly **one** shape: a single **supervised tabular dataset** — one
rectangular table (rows × columns) plus a chosen target column — which is what the existing
`datasets` catalog, `infer_metadata`, and the training flow already understand (see the Upload-CSV
and Add-from-OpenML paths in the Datasets section).

The design answer to "Kaggle is too broad" is therefore **inversion**: we do not try to adapt to
Kaggle. We define the narrow target shape the system already eats, then make every Kaggle import
pass through an **ordered, extensible set of adaptability rules** that either normalise the dataset
into that shape or **reject it with a human-readable reason**. "Adding a rule" means appending one
named rule unit; the import flow and UI never change. This is the same fail-fast / shift-left idea
used in the project's CI: catch the mismatch early, explain it clearly.

## User Scenarios & Testing *(mandatory)*

The "user" is the **researcher/operator** managing the dataset catalog. Today they add datasets by
uploading a CSV or pasting an OpenML task id. This feature adds a third on-ramp — a public Kaggle
dataset link — without changing what a "dataset" means downstream. US1 alone (import a clean
single-table dataset) is a viable MVP.

### User Story 1 - Import a single-table public Kaggle dataset by link (Priority: P1)

The researcher pastes the URL of a public Kaggle **dataset** that contains one tabular file, picks
which column is the prediction target, and the dataset lands in the catalog exactly like an uploaded
CSV — stored, profiled (task type, instance/feature counts, class balance, size tier), and
selectable for training.

**Why this priority**: This is the feature's anchor value — a new, low-friction source for the
catalog. It reuses the entire existing ingestion path (object store + `datasets` row + metadata
inference), so delivering it alone is a complete, demonstrable slice.

**Independent Test**: Point the console at a known public single-table Kaggle dataset URL, choose
the target column, confirm a new catalog row appears with correct task type and counts and that the
dataset is offered in the training-run configuration — with no manual download or file handling.

**Acceptance Scenarios**:

1. **Given** valid Kaggle credentials and a public dataset URL with one tabular file, **When** the
   user fetches and selects a target column and confirms import, **Then** a `datasets` row is created
   (source = Kaggle) with task type, instance/feature counts, class balance, and size tier inferred,
   and the file is stored in the object store.
2. **Given** a dataset already imported earlier, **When** the user imports the same Kaggle dataset
   again, **Then** the system points to the existing catalog entry instead of creating a duplicate.
3. **Given** a successful import, **When** the user opens the training-run configuration, **Then** the
   imported dataset is selectable identically to uploaded/OpenML datasets.

---

### User Story 2 - See exactly why a dataset is or isn't adaptable (Priority: P2)

When a pasted link does not fit the target shape — a competition link, an image-only dataset, a file
over the size cap, a multi-file dataset with nothing selected, or a column that can't be a target —
the user sees a clear checklist of the adaptability rules with the **specific rule that failed and
why**, plus a hint on what to do. No silent failures, no opaque stack traces.

**Why this priority**: This is the heart of "Kaggle is too broad to adapt." It turns an unbounded
problem into a transparent, bounded one: the user always knows whether a given dataset is usable and
why. It is independently valuable even before the catalog of supported shapes grows.

**Independent Test**: Feed each unsupported input class (competition URL, image-only dataset,
oversized file, multi-file with no pick, all-unique target) and confirm each yields a distinct,
named, human-readable rejection — with the import stopping at the first failed rule.

**Acceptance Scenarios**:

1. **Given** a Kaggle **competition** URL, **When** the user fetches it, **Then** the import is
   rejected with a reason naming the URL-shape rule and a hint that v1 supports public Datasets only.
2. **Given** a dataset with no tabular file (e.g. images only), **When** the user fetches it, **Then**
   the import is rejected with a reason naming the tabular-file rule.
3. **Given** a tabular file larger than the configured size cap, **When** the user fetches it, **Then**
   the import is rejected with a reason stating the limit and the file's size.
4. **Given** missing Kaggle credentials, **When** the user attempts any import, **Then** the import is
   rejected early with setup guidance (a public link still requires an API token).

---

### User Story 3 - Choose which file to import from a multi-file dataset (Priority: P3)

When a Kaggle dataset bundles several tabular files (the common `train.csv` / `test.csv` /
`sample_submission.csv` pattern), the user picks which file becomes the dataset rather than the
system guessing.

**Why this priority**: Multi-file datasets are common on Kaggle, but the single-file case (US1) is a
complete MVP on its own; file selection is an enhancement layered on top.

**Independent Test**: Fetch a dataset with multiple tabular files, confirm a file picker lists the
candidates, select one, and confirm only that file is imported and profiled.

**Acceptance Scenarios**:

1. **Given** a dataset with multiple tabular files, **When** the user fetches it, **Then** a picker
   lists the tabular candidates and no import happens until one is chosen.
2. **Given** a chosen file, **When** the user selects a target column and confirms, **Then** only that
   file is downloaded, profiled, and added to the catalog.

### Edge Cases

- **Missing / invalid credentials** → rejected early with setup guidance.
- **Private, deleted, or 404 dataset** → rejected with the access reason returned by Kaggle.
- **Competition or kernel/code URL** → rejected by the URL-shape rule (out of scope for v1).
- **Image / audio / text-only dataset (no tabular file)** → rejected by the tabular-file rule.
- **Multiple tabular files** → file picker required before import (US3).
- **Oversized file** → rejected by the size rule with the limit and the actual size.
- **Unusual CSV** (odd delimiter, non-UTF-8, ragged rows, <2 columns) → rejected by the parse/shape
  rule with a readable reason; no partial row written.
- **Target column is an identifier** (unique per row) or all-null → rejected by the target-validity
  rule unless it is a valid continuous regression target.
- **Duplicate import** (same dataset+file already in catalog) → points to the existing entry.
- **Kaggle API timeout / network failure** → surfaced as a transient error the user can retry; no
  catalog row written.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Datasets section MUST provide a third ingestion control that accepts a public
  Kaggle dataset URL, alongside the existing Upload-CSV and Add-from-OpenML controls.
- **FR-002**: The system MUST validate that the URL refers to a Kaggle **dataset** and reject
  competition, kernel/code, and non-Kaggle URLs with a human-readable reason.
- **FR-003**: The system MUST authenticate to Kaggle using operator-provided credentials; when
  credentials are absent it MUST reject the import early with setup guidance (a public link still
  requires an API token — there is no anonymous bulk download).
- **FR-004**: The system MUST enumerate the dataset's files and identify the tabular candidates
  (delimited text and columnar table formats).
- **FR-005**: The system MUST use the single tabular file when exactly one exists, let the user
  select when several exist, and reject when none exist — each with a clear reason.
- **FR-006**: The system MUST enforce a configurable maximum import file size and reject oversized
  files, stating both the limit and the actual size.
- **FR-007**: Users MUST select the target column; the system MUST validate the selection yields a
  supported task type (binary, multiclass, or regression) and reject selections that cannot
  (e.g. a per-row identifier or an all-null column).
- **FR-008**: On a full pass the system MUST store the file in the object store and create a
  `datasets` catalog row (source = Kaggle) using the existing metadata inference, so the dataset is
  selectable for training identically to uploaded/OpenML datasets.
- **FR-009**: Import eligibility MUST be expressed as an **ordered, extensible set of named rules**.
  Each rule yields pass or reject with a human-readable reason and a hint. Adding, removing, or
  reordering a rule MUST NOT require changes to the import orchestration or the UI.
- **FR-010**: The system MUST surface the rule outcome to the user — which rules passed, which failed,
  and why — and MUST stop at the first failed rule (fail-fast).
- **FR-011**: The system MUST treat downloaded content as data only: never execute it, read only
  recognised tabular formats, and guard archive expansion (no unbounded extraction).
- **FR-012**: The system MUST de-duplicate — when the same Kaggle dataset+file has already been
  imported, point to the existing catalog entry rather than creating a duplicate.
- **FR-013**: The import and rejection behaviour MUST be verifiable without live network access to
  Kaggle (the Kaggle access seam MUST be mockable), so automated tests stay hermetic.

### Key Entities *(include if feature involves data)*

- **Kaggle dataset reference**: the parsed `owner/slug` and canonical URL of a public dataset.
- **Adaptability rule**: a named, ordered eligibility check with a description; produces a verdict.
- **Rule verdict**: pass or reject, a human-readable reason, and an optional remediation hint.
- **Import session**: the transient multi-step state of one import (URL → file list → chosen file →
  chosen target), distinct from a persisted dataset.
- **Dataset record**: the existing catalog entry (`datasets` row) — reused unchanged, with source
  marking the Kaggle origin.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can import a known single-table public Kaggle dataset and see it in the catalog
  in under one minute, performing no manual download, unzip, or file handling.
- **SC-002**: 100% of rejected imports name the specific failed rule and state a reason — there are no
  silent failures and no raw stack traces shown for an unsupported dataset.
- **SC-003**: Adding a new adaptability rule changes only the rule set (one new rule unit) — zero
  edits to the import orchestration or the catalog UI.
- **SC-004**: The full automated test suite covering import and every rejection class runs offline
  (no network), keeping CI green and within its current runtime budget.
- **SC-005**: An imported Kaggle dataset is indistinguishable downstream from an uploaded or OpenML
  dataset — same catalog columns, selectable for training, profiled with task type and counts.

## Assumptions

- **Scope is Kaggle Datasets only.** Competitions and kernels/code are out of scope for v1
  (competition data requires per-competition rule acceptance and heavier auth) — rejected with a
  reason, not silently.
- **Target shape is a single supervised tabular dataset.** Image, audio, text, and multi-table
  datasets are out of scope and rejected with reasons; this is the deliberate boundary that keeps
  "all of Kaggle" tractable.
- **Credentials are operator-provided** via the standard Kaggle token (environment variables or the
  standard token file) and passed into the deployed console; the API key is never stored in the
  application database.
- **The existing ingestion path is reused** — object store + `datasets` row + metadata inference —
  so Kaggle datasets behave like every other dataset downstream.
- **Default size cap** is a reasonable bound (≈200 MB) configurable via environment, chosen to
  protect a small VPS and the object store and to keep tests fast.
- **One Kaggle import is interactive and single-user** (matching the console's current model); no
  background queue is introduced.
