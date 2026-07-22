"""Backend HTTP API (spec 007) — a thin FastAPI layer over the storage/ services.

Additive: runs beside the Streamlit console (single source of truth). Every handler wraps an
existing storage function; the only business logic lives in storage/, not here.
"""
