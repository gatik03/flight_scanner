"""Stable application exception types."""


class AppError(Exception):
    """Base class for errors that can be mapped to a client response."""

    code = "application_error"
    status_code = 500
    title = "Application error"

    def __init__(self, detail: str = "The request could not be completed.") -> None:
        super().__init__(detail)
        self.detail = detail


class ValidationError(AppError):
    code = "validation_error"
    status_code = 422
    title = "Validation error"


class InfrastructureError(AppError):
    code = "infrastructure_error"
    status_code = 503
    title = "Service unavailable"
