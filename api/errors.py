"""One error shape for the whole API (FR-007): {"error": {"code", "message"}}.

Routers raise `ApiError(code, message, http_status)` for expected failures; a catch-all handler turns
any unexpected exception into a generic 500 — never a stack trace, never a secret (SC-003).
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("api")


class ApiError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        self.code, self.message, self.http_status = code, message, http_status
        super().__init__(message)


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError):
        return JSONResponse(status_code=exc.http_status, content=_body(exc.code, exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 413: "too_large", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content=_body("invalid_input", "request validation failed"))

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, _exc: Exception):
        log.exception("unhandled API error")                 # logged server-side; body stays generic
        return JSONResponse(status_code=500, content=_body("internal_error", "internal server error"))
