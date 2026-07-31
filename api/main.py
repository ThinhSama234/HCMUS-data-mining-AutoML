"""FastAPI app (spec 007). Thin HTTP layer over storage/; additive beside Streamlit.

    uvicorn api.main:app --port 8000      # console stays on 8501

All routes are under /api/v1. Docs: /api/v1/docs · schema: /api/v1/openapi.json.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors import register_error_handlers
from api.routers import cost, datasets, deployments, methods, results, training

API_VERSION = "v1"
CONTRACT_VERSION = "0.1.0"

DESCRIPTION = """
HTTP/JSON access to the AutoML benchmark backend — the same engine the Streamlit console uses,
exposed for non-Streamlit clients (a web UI, a decision assistant, scripts).

**Thin layer:** every route wraps a `storage/` module; no business logic is duplicated here.

**Conventions**
- All routes live under `/api/v1`.
- List endpoints return a page envelope: `{items, total, limit, offset}` (`limit` ≤ 200).
- Errors share one shape: `{"error": {"code", "message"}}` — never a stack trace or secret.
- Long jobs (launch a run, integrate a method) return **202** with a `poll` URL; poll it for status.
"""

app = FastAPI(
    title="AutoML Bench API",
    version=CONTRACT_VERSION,
    description=DESCRIPTION,
    docs_url=f"/api/{API_VERSION}/docs",
    openapi_url=f"/api/{API_VERSION}/openapi.json",
)

# CORS for a future web frontend on another origin (empty = disabled). FR-010/D9.
_origins = [o.strip() for o in os.environ.get("API_CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins,
                       allow_methods=["*"], allow_headers=["*"])

register_error_handlers(app)

v1 = APIRouter(prefix=f"/api/{API_VERSION}")


@v1.get("/health", tags=["meta"], summary="Liveness probe")
def health():
    """Return `{"status": "ok"}` if the app is up. Used by Docker/monitoring health checks."""
    return {"status": "ok"}


@v1.get("/version", tags=["meta"], summary="API + contract version")
def version():
    """Report the URL version (`v1`) and the response-contract version clients can pin against."""
    return {"api": API_VERSION, "contract": CONTRACT_VERSION}


for _r in (datasets.router, methods.router, training.router, results.router,
           deployments.router, cost.router):
    v1.include_router(_r)

app.include_router(v1)
