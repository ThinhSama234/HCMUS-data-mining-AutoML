"""Cost — estimate a run's compute cost. Wraps the shared storage.cost.estimate()."""
from fastapi import APIRouter

from api import schemas
from storage import cost as cost_svc

router = APIRouter(prefix="/cost", tags=["cost"])


@router.post("/estimate")
def estimate(body: schemas.CostEstimateIn):
    return cost_svc.estimate(body.datasets, body.frameworks, body.constraint)
