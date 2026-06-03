"""Shape uniforme de error y handlers (F2 §6.1, §6.6).

Todas las respuestas de error siguen `{"error": {"code": str, "message": str,
"details": object|null}}`. `code` es estable y legible por máquina.
"""
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Excepción propia del backend con código estable.

    Lánzala en lugar de `HTTPException` cuando quieras controlar el `code`
    expuesto al cliente. Para errores ad-hoc, usa `HTTPException` y el handler
    deriva el `code` del status.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _envelope(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def _code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable_entity",
        502: "bad_gateway",
        503: "service_unavailable",
    }.get(status_code, "internal_error")


async def _api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.code, exc.message, exc.details),
    )


async def _http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(_code_for_status(exc.status_code), str(exc.detail)),
    )


async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_envelope("bad_request", "Validation error", {"errors": exc.errors()}),
    )


async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    # No filtrar `repr(exc)` al cliente: solo el código + mensaje genérico.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope("internal_error", "Unexpected error"),
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
