"""Structured logging with request ID correlation.

Provides a middleware that attaches a UUID request ID to every request,
making it available in log output for end-to-end tracing. Also improves
the base log format with structured fields.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s %(levelname)s %(name)s "
            "[%(request_id)s] %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Inject a default request_id so log lines outside requests don't fail.
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return record

    logging.setLogRecordFactory(record_factory)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and response.

    The request ID is:
    1. Taken from the ``X-Request-ID`` header if present.
    2. Generated as a UUID4 otherwise.

    The ID is injected into the logging context so all log lines during the
    request include it, and returned in the response header for tracing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

        # Inject into logging context for this request's thread.
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.request_id = request_id
            return record

        logging.setLogRecordFactory(record_factory)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logging.getLogger(__name__).exception(
                "Unhandled error on %s %s", request.method, request.url.path,
            )
            raise
        finally:
            logging.setLogRecordFactory(old_factory)

        elapsed_ms = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        logger = logging.getLogger("app.access")
        logger.info(
            "%s %s -> %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
