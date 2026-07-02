# Contract — Kaggle access seam (`storage/kaggle_client.py`)

A thin, **mockable** wrapper over the official Kaggle API. This is the only place that imports
`kaggle` or touches the network. It mirrors the `integration._container_cli` pattern (a seam over an
external dependency) so tests inject a fake and stay hermetic (FR-013).

## Interface (duck-typed)

```text
parse_url(url: str) -> Ref | None
    # "https://www.kaggle.com/datasets/owner/slug"  -> Ref(owner="owner", slug="slug")
    # competition/kernel/other host                 -> None   (R1 rejects on None)

list_files(ref: Ref) -> list[FileInfo]
    # FileInfo: { name: str, size_bytes: int | None }
    # raises KaggleAccessError on 403/404/network (R3 turns this into a reject)

file_size(ref: Ref, name: str) -> int | None        # bytes, if known from listing

download_file(ref: Ref, name: str, max_bytes: int) -> bytes
    # single-file download; if only a whole-dataset zip is available, extract just `name`
    # with a bounded extractor — raise if uncompressed size > max_bytes (zip-bomb guard, FR-011)
```

`Ref` is a tiny value object `{owner, slug}` with `.path -> "owner/slug"` and
`.canonical_url`.

## Auth behaviour (R2)

- Credentials come from `KAGGLE_USERNAME`+`KAGGLE_KEY` or `~/.kaggle/kaggle.json`.
- **Lazy import**: the real client is imported and authenticated **inside** the factory, never at
  module import — so the app boots and tests run without a token. `credentials_present() -> bool`
  reports config state for R2 without performing a network call.

## Factory + test injection

```text
get_client() -> KaggleClient        # returns the real client (lazy-imports `kaggle`); cached
set_client(fake) -> None            # tests inject a fake; reset with set_client(None)
```

The fake used in tests is any object implementing the four methods above, backed by
`tests/fixtures/kaggle_*` directories:

| Fixture | Shape | Drives |
|---|---|---|
| `kaggle_single/` | one `data.csv` | happy path (US1) |
| `kaggle_multi/` | `train.csv`, `test.csv`, `sample_submission.csv` | file picker (US3) |
| `kaggle_images/` | manifest with `.jpg` only, no table | R4 reject |
| (params) | a `FileInfo` with `size_bytes` over cap | R5 reject |

## Errors

- `KaggleAccessError(reason)` — listing/download failures (private/404/network). Caught by the
  ingest layer and turned into an R3 verdict or a transient UI error; **never** a raw stack trace
  (SC-002).
- Oversized extraction raises before returning bytes (FR-011).
