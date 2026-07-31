"""Request models + response field whitelists (FR-011: never dump a raw row / secret).

Responses are built by `pick()`-ing an explicit set of fields from the storage records, so secrets
(storage URIs, checksums, credentials) never leak. Request bodies are Pydantic models (validated +
documented in OpenAPI).
"""
from typing import List, Optional

import pandas as pd
from pydantic import BaseModel, Field

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


# --- request bodies (Field descriptions/examples surface in the Swagger docs) ---
class OpenmlIngestIn(BaseModel):
    task_id: int = Field(description="OpenML task id to ingest", examples=[3573])


class KaggleListIn(BaseModel):
    url: str = Field(description="Public Kaggle dataset URL to screen",
                     examples=["https://www.kaggle.com/datasets/owner/slug"])


class KaggleImportIn(BaseModel):
    url: str = Field(description="Public Kaggle dataset URL",
                     examples=["https://www.kaggle.com/datasets/owner/slug"])
    file_name: str = Field(description="File within the dataset to import (from /kaggle/list)",
                           examples=["data.csv"])
    target_column: str = Field(description="Column to use as the prediction target",
                               examples=["label"])


class LaunchRunIn(BaseModel):
    method: str = Field(description="Integrated method name to run", examples=["RandomForest"])
    dataset_ids: Optional[List[int]] = Field(
        default=None, description="Datasets to run on; omit to use all runnable ones",
        examples=[[1, 2]])
    constraint: Optional[str] = Field(
        default=None, description="Time/resource budget; omit for the default (`smoke`)",
        examples=["smoke"])


class CostEstimateIn(BaseModel):
    datasets: int = Field(description="Number of datasets in the run", examples=[10])
    frameworks: int = Field(description="Number of frameworks to run", examples=[3])
    constraint: Optional[str] = Field(
        default=None, description="Constraint whose time budget drives the estimate",
        examples=["smoke"])
