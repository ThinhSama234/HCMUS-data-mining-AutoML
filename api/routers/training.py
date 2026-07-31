"""Training runs — launch (async handle), poll, stop, and launch options. Wraps storage.runner."""
from fastapi import APIRouter, Depends

from api import deps, schemas
from api.errors import ApiError
from storage import runner

router = APIRouter(tags=["training"])

_FETCH = 500  # jobs fetched before in-memory pagination (single-user scale)


def _jobs():
    df = runner.list_jobs(limit=_FETCH)
    return df.to_dict("records") if df is not None and not df.empty else []


@router.get("/training-runs", summary="List training runs")
def list_runs(pg: deps.Pagination = Depends(deps.pagination)):
    """Paginated history of benchmark runs with status, framework, constraint, and timestamps."""
    recs = _jobs()
    items = [schemas.pick(r, schemas.RUN_FIELDS) for r in recs[pg.offset:pg.offset + pg.limit]]
    return deps.page(items, len(recs), pg)


@router.post("/training-runs", status_code=202, summary="Launch a training run")
def launch_run(body: schemas.LaunchRunIn):
    """Start a benchmark run for a method over its runnable datasets (async). Returns **202** with
    `{id, status, poll}` — GET the `poll` URL for progress. **400 invalid_input** if the method
    isn't integrated or has no runnable datasets. `dataset_ids`/`constraint` are optional
    (constraint defaults to `smoke`)."""
    tr_id, status = runner.launch(body.method, body.dataset_ids,
                                  body.constraint or runner.DEFAULT_CONSTRAINT)
    if tr_id is None:
        raise ApiError("invalid_input", f"cannot launch ({status}): method must be integrated "
                       "and have runnable datasets", 400)
    return {"kind": "training_run", "id": tr_id, "status": status,
            "poll": f"/api/v1/training-runs/{tr_id}"}


@router.get("/training-runs/{tr_id}", summary="Get a training run")
def get_run(tr_id: int):
    """Poll a single run's status by id. **404** if unknown."""
    row = next((r for r in _jobs() if r.get("training_run_id") == tr_id), None)
    if not row:
        raise ApiError("not_found", f"training run {tr_id} not found", 404)
    return schemas.pick(row, schemas.RUN_FIELDS)


@router.post("/training-runs/{tr_id}/stop", summary="Stop a training run")
def stop_run(tr_id: int):
    """Request cancellation of a run. Returns `{training_run_id, cancelled}` (`cancelled=false`
    if it had already finished or wasn't cancellable)."""
    return {"training_run_id": tr_id, "cancelled": runner.cancel(tr_id)}


@router.get("/training/options", summary="Launch form options")
def launch_options():
    """Everything a client needs to build a launch request: runnable `methods`, available
    `constraints`, and trainable `datasets`."""
    return {
        "methods": runner.list_runnable(),
        "constraints": runner.list_constraints(),
        "datasets": runner.list_trainable_datasets(),
    }
