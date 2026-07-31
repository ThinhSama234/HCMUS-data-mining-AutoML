"""Results — the tidy leaderboard frame, filterable + paginated. Wraps storage.repo.load()."""
from fastapi import APIRouter, Depends

from api import deps, schemas

router = APIRouter(prefix="/results", tags=["results"])


@router.get("", summary="List benchmark results")
def list_results(pg: deps.Pagination = Depends(deps.pagination),
                 framework: str = "", type: str = "", dataset: str = ""):
    """Paginated leaderboard rows (framework, task, metric, score, success). Optional exact-match
    filters: `framework`, `type` (task type), `dataset` (task name). Empty filter = no filter."""
    from storage import repo
    df = repo.load()
    if df is None or df.empty:
        recs = []
    else:
        if framework:
            df = df[df["framework"] == framework]
        if type:
            df = df[df["type"] == type]
        if dataset:
            df = df[df["task"] == dataset]
        recs = df.to_dict("records")
    items = [schemas.pick(r, schemas.RESULT_FIELDS) for r in recs[pg.offset:pg.offset + pg.limit]]
    return deps.page(items, len(recs), pg)
