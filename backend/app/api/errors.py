"""Problem-details style exception handlers."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import AppError


def problem_details(
    request: Request, status_code: int, title: str, detail: str, code: str
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"https://flight-deal-aggregator.dev/problems/{code}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "code": code,
            "request_id": request_id,
        },
        media_type="application/problem+json",
    )


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await unhandled_error_handler(request, exc)
    return problem_details(request, exc.status_code, exc.title, exc.detail, exc.code)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await unhandled_error_handler(request, exc)
    return problem_details(
        request,
        422,
        "Validation error",
        "The request contains invalid data.",
        "validation_error",
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return problem_details(
        request,
        500,
        "Internal server error",
        "The server could not complete the request.",
        "internal_error",
    )
