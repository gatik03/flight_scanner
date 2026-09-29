"""HTTP middleware and structured logging setup."""

import logging
import re
from typing import Any
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, reset_contextvars
from structlog.types import EventDict

SECRET_PATTERN = re.compile(r"(?i)(token|secret|password|api[_-]?key)=([^&\s]+)")
logger = structlog.get_logger(__name__)


def redact_secrets(_: Any, __: str, event_dict: EventDict) -> EventDict:  # noqa: ANN401
    """Redact common secret-shaped values before JSON rendering."""

    for key in tuple(event_dict):
        if any(word in key.lower() for word in ("token", "secret", "password", "api_key")):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], str):
            event_dict[key] = SECRET_PATTERN.sub(r"\1=[REDACTED]", event_dict[key])
    return event_dict


def configure_logging(log_level: str) -> None:
    numeric_level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redact_secrets,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=False,
    )


class RequestIdMiddleware:
    """Attach or create a request id and return it in every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = next(
            (value.decode() for key, value in scope["headers"] if key == b"x-request-id"),
            str(uuid4()),
        )
        scope["state"] = {**scope.get("state", {}), "request_id": request_id}
        context_tokens = bind_contextvars(request_id=request_id)
        response_status = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request_completed",
                method=scope.get("method", ""),
                path=scope.get("path", ""),
                status_code=response_status,
            )
            reset_contextvars(**context_tokens)
