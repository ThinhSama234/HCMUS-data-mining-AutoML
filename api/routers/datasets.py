"""Datasets — read the catalog + ingest (upload / OpenML / Kaggle). Wraps storage.ingest + repo."""
from fastapi import APIRouter, Depends, File, UploadFile

from api import deps, schemas
from api.errors import ApiError
from storage import ingest, kaggle_client, repo

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _records():
    df = repo.list_datasets()
    return df.to_dict("records") if not df.empty else []


def _one(dataset_id: int) -> dict:
    row = next((r for r in _records() if r.get("dataset_id") == dataset_id), None)
    return schemas.pick(row, schemas.DATASET_FIELDS) if row else {"dataset_id": dataset_id}


@router.get("", summary="List datasets")
def list_datasets(pg: deps.Pagination = Depends(deps.pagination)):
    """Paginated catalog of datasets (upload / OpenML / Kaggle), newest first. Returns a page
    envelope; each item is the whitelisted dataset fields (name, source, task_type, shape, status…)."""
    recs = _records()
    items = [schemas.pick(r, schemas.DATASET_FIELDS) for r in recs[pg.offset:pg.offset + pg.limit]]
    return deps.page(items, len(recs), pg)


@router.get("/{dataset_id}", summary="Get one dataset")
def get_dataset(dataset_id: int):
    """Fetch a single dataset by numeric id. **404** if no such dataset exists."""
    row = next((r for r in _records() if r.get("dataset_id") == dataset_id), None)
    if not row:
        raise ApiError("not_found", f"dataset {dataset_id} not found", 404)
    return schemas.pick(row, schemas.DATASET_FIELDS)


@router.post("/upload", summary="Ingest an uploaded CSV")
def ingest_upload(file: UploadFile = File(...)):
    """Upload a CSV file (multipart/form-data). Parses + profiles it, stores it, and catalogs a
    `source=upload` dataset. **400 invalid_input** if the bytes aren't a readable CSV."""
    try:
        did = ingest.ingest_upload(file.file.read(), file.filename or "upload.csv")
    except ValueError as exc:
        raise ApiError("invalid_input", str(exc), 400)
    return _one(did)


@router.post("/openml", summary="Ingest an OpenML task")
def ingest_openml(body: schemas.OpenmlIngestIn):
    """Fetch an OpenML task by id, store its dataset, and catalog a `source=openml` dataset
    (de-duped: re-ingesting the same task returns the existing one). **502** if OpenML is
    unreachable."""
    try:
        did = ingest.ingest_openml(body.task_id)
    except Exception as exc:                              # openml/network failure → transient
        raise ApiError("upstream_error", f"OpenML fetch failed: {exc}", 502)
    return _one(did)


@router.post("/kaggle/list", summary="Preview a Kaggle dataset link")
def kaggle_list(body: schemas.KaggleListIn):
    """Screen a public Kaggle dataset URL **before** downloading: parse the URL, check credentials,
    and list files. Returns the file list plus per-rule verdicts (`ok`/`reason`/`hint`) and an
    overall `ok`. Downloads nothing — use `/kaggle/import` to actually ingest."""
    listing = ingest.kaggle_list(body.url)
    ref = {"owner": listing.ref.owner, "slug": listing.ref.slug} if listing.ref else None
    return {
        "ref": ref,
        "files": [{"name": f.name, "size_bytes": f.size_bytes} for f in listing.files],
        "verdicts": [{"ok": v.ok, "rule_id": v.rule_id, "reason": v.reason, "hint": v.hint}
                     for v in listing.verdicts],
        "ok": listing.ok,
    }


@router.post("/kaggle/import", summary="Import a Kaggle dataset file")
def kaggle_import(body: schemas.KaggleImportIn):
    """Download one file from a public Kaggle dataset URL, validate it against the rule pipeline
    (URL shape, size, table shape, target column), and catalog a `source=kaggle` dataset.
    **422 rule_rejected** with the failing rule id/reason if any rule blocks it (e.g. a competition
    URL, oversized file, missing target). Returns `{dataset_id, deduped}`."""
    ref = kaggle_client.parse_url(body.url)
    if ref is None:
        raise ApiError("rule_rejected", "R1-url-shape — not a Kaggle dataset URL", 422)
    staged = ingest.kaggle_read(ref, body.file_name)
    if not staged.ok:
        v = next((x for x in staged.verdicts if not x.ok), None)
        raise ApiError("rule_rejected", f"{v.rule_id} — {v.reason}" if v else "read failed", 422)
    res = ingest.kaggle_import(staged, body.target_column)
    if not res.ok:
        v = next((x for x in res.verdicts if not x.ok), None)
        raise ApiError("rule_rejected", f"{v.rule_id} — {v.reason}" if v else "import failed", 422)
    return {"dataset_id": res.dataset_id, "deduped": res.deduped}
