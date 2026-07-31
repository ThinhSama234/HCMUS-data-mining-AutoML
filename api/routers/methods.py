"""Methods — browse + integrate (async handle + poll). Wraps storage.repo + storage.integration."""
from fastapi import APIRouter, Depends

from api import deps, schemas
from api.errors import ApiError
from storage import integration, repo

router = APIRouter(prefix="/methods", tags=["methods"])


@router.get("", summary="List methods")
def list_methods(pg: deps.Pagination = Depends(deps.pagination)):
    """Paginated catalog of AutoML methods with kind, version, preset, integration status, and
    Docker image info."""
    df = repo.list_methods()
    recs = df.to_dict("records") if not df.empty else []
    items = [schemas.pick(r, schemas.METHOD_FIELDS) for r in recs[pg.offset:pg.offset + pg.limit]]
    return deps.page(items, len(recs), pg)


@router.get("/{name}", summary="Get one method")
def get_method(name: str):
    """Fetch a single method by name. **404** if unknown."""
    m = repo.get_method(name)
    if not m:
        raise ApiError("not_found", f"method {name} not found", 404)
    return schemas.pick(m, schemas.METHOD_FIELDS)


@router.post("/{name}/integrate", status_code=202, summary="Integrate a method")
def integrate(name: str):
    """Build/validate a method's Docker integration (async, detached worker). Returns **202** with
    `{id, status, poll}` — GET the `poll` URL (`/methods/{name}/status`) for progress."""
    status = integration.integrate(name)                  # detached worker; returns immediate status
    return {"kind": "integration", "id": name, "status": status,
            "poll": f"/api/v1/methods/{name}/status"}


@router.get("/{name}/status", summary="Integration status")
def method_status(name: str):
    """Poll the integration progress/result for a method (pairs with POST `/integrate`)."""
    return integration.integration_status(name)
