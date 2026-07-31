"""Deployments — list catalog deployments (read-only). Thin select over the deployments table."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from api import deps, schemas
from storage import db
from storage.models import deployments as deployments_tbl

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("", summary="List deployments")
def list_deployments(pg: deps.Pagination = Depends(deps.pagination)):
    """Paginated catalog of model deployments (read-only): endpoint URL, status, p95 latency,
    and deploy time, newest first."""
    eng = db.init_db()
    with eng.connect() as c:
        recs = [dict(r._mapping) for r in c.execute(
            select(deployments_tbl).order_by(deployments_tbl.c.deployment_id.desc()))]
    items = [schemas.pick(r, schemas.DEPLOYMENT_FIELDS) for r in recs[pg.offset:pg.offset + pg.limit]]
    return deps.page(items, len(recs), pg)
