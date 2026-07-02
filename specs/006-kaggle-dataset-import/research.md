# Phase 0 — Research & Decisions

Resolves the unknowns implied by the spec. Each item: **Decision · Rationale · Alternatives**.

## D1 — How to connect to a "public" Kaggle dataset

**Decision**: Use the official **`kaggle` PyPI package** (`KaggleApi`), authenticated via
`KAGGLE_USERNAME` + `KAGGLE_KEY` environment variables (or a `~/.kaggle/kaggle.json` token).

**Rationale**: Kaggle exposes **no anonymous bulk-download endpoint** — even a *public* dataset
requires an authenticated API token. The official client is the supported, stable path and gives
file-level listing and download. This directly shapes rule **R2 (credentials present)**: "public
link" does **not** mean "no auth", and the UI must say so.

**Alternatives**:
- `kagglehub` — newer, still requires auth, less file-level control. Viable later; not v1.
- Scraping the dataset HTML / unofficial download URLs — fragile, breaks on markup change, violates
  ToS. Rejected.

**Gotcha to handle**: the `kaggle` package historically **authenticates at import time** and raises
if no token is present. To keep app boot and hermetic tests working without credentials, the seam
imports the client **lazily** (inside `get_client()`), never at module import.

## D2 — File-level download vs whole-dataset zip

**Decision**: Prefer the single-file download (`dataset_download_file(owner/slug, file_name)`); if the
client only returns the whole-dataset zip, extract **only the chosen file** with a bounded extractor
(reject if the uncompressed size exceeds the cap — zip-bomb guard, FR-011).

**Rationale**: Importing one table shouldn't pull a multi-GB bundle. File-level fetch keeps imports
fast and within the size cap.

**Alternatives**: Always download the full zip then pick — wastes bandwidth and can blow the cap
before any check runs. Rejected as the default.

## D3 — Two-phase rule evaluation

**Decision**: Split rules into **pre-download** (cheap, metadata only: URL shape, credentials,
reachability, tabular-file presence, declared size) and **post-selection** (needs bytes/sample:
parse/shape, target validity). The engine runs a phase as an ordered list, **fail-fast** at the first
reject.

**Rationale**: Never transfer bytes for a dataset that fails on URL shape or size. Matches the
UI round-trip (fetch → select → import) and the project's shift-left instinct.

**Alternatives**: One post-download phase — simpler but downloads before cheap checks. Rejected.

## D4 — Size cap

**Decision**: `KAGGLE_MAX_FILE_MB` env, default **200**. Enforced first against the file size reported
by the listing (pre-download); re-checked against actual bytes after download.

**Rationale**: Protects the small VPS and the object store; keeps tests fast. Configurable so heavier
hosts can raise it.

## D5 — Target-column selection

**Decision**: After a file is chosen, read **only a header + small sample** (e.g. `nrows≈1000`) to
populate the target-column picker quickly; do the full read at import time. Do **not** assume the last
column is the target (Kaggle CSVs often lead with id/index columns) — extend `infer_metadata`'s
existing `target_column` parameter, which already accepts an explicit target.

**Rationale**: Fast, accurate picker; reuses the metadata function that already supports an explicit
target (the OpenML path passes one today).

## D6 — Hermetic testing seam

**Decision**: All Kaggle access goes through `storage/kaggle_client.py::get_client()`, returning an
object with a small duck-typed interface (`parse_url`, `list_files`, `file_size`, `download_file`).
Tests call `set_client(fake)` (or monkeypatch the factory) to inject a fake backed by
`tests/fixtures/kaggle_*`. No network, no credentials needed in CI.

**Rationale**: Mirrors `integration._container_cli` (seam over an external dependency) and satisfies
FR-013 / SC-004. The Tier-1 CI lesson — a non-hermetic test that depended on ambient state — is
explicitly avoided here.

**Alternatives**: Hit live Kaggle in tests — flaky, slow, needs secrets in CI, rate-limited.
Rejected.

## D7 — Where the imported dataset is recorded (no migration)

**Decision**: Reuse the `datasets` table. Set `source="kaggle"`, `file_format="csv"`, `storage_uri`
to the object-store key, `checksum_sha256` to the file hash, `status="ready"`, plus the inferred
metadata. **No schema change** — `source` is a free-text column (the `upload|openml|import` comment is
advisory; update the comment to mention `kaggle`).

**Rationale**: Keeps Kaggle datasets identical downstream (SC-005); avoids a migration.

## D8 — De-duplication

**Decision**: De-dupe by **content checksum** (`checksum_sha256`) — compute the SHA-256 of the
downloaded file; if a `datasets` row with that checksum already exists, return it instead of inserting
(mirrors how the OpenML path de-dupes by `openml_task_id`). The catalog `name` is derived
(`"kaggle:{owner}/{slug}/{file}"`) and the existing `name` unique-constraint is honoured by checking
first.

**Rationale**: Robust across re-imports and even across sources (same file uploaded twice). Reuses an
existing column.

**Alternatives**: A new `kaggle_ref` column — needs a migration and only de-dupes within Kaggle.
Deferred.

## Resolved unknowns

| Spec item | Resolution |
|---|---|
| Kaggle access method | Official `kaggle` client, env/token auth (D1) |
| "Public link" auth | Still requires a token → rule R2 + UI guidance (D1, D2) |
| Multi-file handling | File-level download + user picker (D2; US3) |
| Size cap value | `KAGGLE_MAX_FILE_MB`, default 200 (D4) |
| Target selection | User-picked via header/sample read; reuse `infer_metadata(target_column=…)` (D5) |
| Hermetic tests | Injectable `get_client()` seam + local fixtures (D6) |
| Storage / migration | Reuse `datasets`, `source="kaggle"`, no migration (D7) |
| Duplicates | By `checksum_sha256` (D8) |
