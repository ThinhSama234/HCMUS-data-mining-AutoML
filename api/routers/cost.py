"""Cost — estimate a run's compute cost. Wraps the shared storage.cost.estimate()."""
from fastapi import APIRouter

from api import schemas
from storage import cost as cost_svc

router = APIRouter(prefix="/cost", tags=["cost"])


@router.post("/estimate", summary="Estimate run compute cost")
def estimate(body: schemas.CostEstimateIn):
    """Upper-bound compute cost for a run of `datasets` × `frameworks` under a `constraint`
    (defaults to `smoke`). No cloud calls — returns total runs, compute hours, and an illustrative
    estimated cost per compute instance (`by_instance`)."""
    return cost_svc.estimate(body.datasets, body.frameworks, body.constraint)
