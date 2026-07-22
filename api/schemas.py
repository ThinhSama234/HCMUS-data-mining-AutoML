"""Request models + response field whitelists (FR-011: never dump a raw row / secret).

Responses are built by `pick()`-ing an explicit set of fields from the storage records, so secrets
(storage URIs, checksums, credentials) never leak. Request bodies are Pydantic models (validated +
documented in OpenAPI).
"""
from typing import List, Optional

import pandas as pd
from pydantic import BaseModel

# --- whitelisted response fields (explicit — no secrets) ---
DATASET_FIELDS = ["dataset_id", "name", "source", "task_type", "target_column", "n_instances",
                  "n_features", "n_classes", "minority_fraction", "size_tier", "file_format",
                  "status", "created_at"]
METHOD_FIELDS = ["method_id", "name", "kind", "version", "preset", "integration_status",
                 "docker_image", "image_tag", "last_integration_at", "last_error", "project_url"]
RUN_FIELDS = ["training_run_id", "status", "mode", "framework", "constraint", "runs", "datasets",
              "started_at", "finished_at", "error"]
RESULT_FIELDS = ["framework", "task", "type", "metric", "result", "score", "success"]
DEPLOYMENT_FIELDS = ["deployment_id", "run_id", "endpoint_url", "status", "p95_latency_ms",
                     "deployed_at"]


def _clean(v):
    """JSON-safe scalar: NaN/NaT → None, numpy scalars → python, datetimes → ISO string."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "item"):
        return v.item()
    return v


def pick(record: dict, fields) -> dict:
    """Project a storage record to the whitelisted fields, JSON-sanitised."""
    return {k: _clean(record.get(k)) for k in fields}


# --- request bodies ---
class OpenmlIngestIn(BaseModel):
    task_id: int


class KaggleListIn(BaseModel):
    url: str


class KaggleImportIn(BaseModel):
    url: str
    file_name: str
    target_column: str


class LaunchRunIn(BaseModel):
    method: str
    dataset_ids: Optional[List[int]] = None
    constraint: Optional[str] = None


class CostEstimateIn(BaseModel):
    datasets: int
    frameworks: int
    constraint: Optional[str] = None
