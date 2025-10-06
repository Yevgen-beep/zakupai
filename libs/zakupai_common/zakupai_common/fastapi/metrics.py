from __future__ import annotations

import time
from collections.abc import Iterable, Sequence

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from zakupai_common.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collects request/response metrics for FastAPI endpoints."""

    def __init__(
        self,
        app,
        service_name: str,
        *,
        skip_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._service = service_name
        self._skip_paths = tuple(skip_paths or ("/metrics", "/health"))

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._skip_paths:
            return await call_next(request)

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        except Exception:  # pragma: no cover - propagated after metrics
            raise
        finally:
            duration = time.perf_counter() - start
            status_code = str(response.status_code if response else 500)

            HTTP_REQUESTS.labels(
                service=self._service,
                method=request.method,
                endpoint=request.url.path,
                status_code=status_code,
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                service=self._service,
                method=request.method,
                endpoint=request.url.path,
            ).observe(duration)


def add_prometheus_middleware(
    app, service_name: str, skip_paths: Sequence[str] | None = None
) -> None:
    """Helper to add Prometheus middleware to FastAPI app."""

    app.add_middleware(
        PrometheusMiddleware, service_name=service_name, skip_paths=skip_paths
    )
