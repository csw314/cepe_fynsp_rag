"""Minimal same-origin static and insights HTTP service with bounded protections."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from cepe_fynsp.insights.prompt import PROMPT_VERSION
from cepe_fynsp.insights.schemas import (
    InsightAiMetadata,
    InsightRequest,
    InsightResponse,
    InsightStatus,
)
from cepe_fynsp.insights.service import InsightService

LOGGER = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Small in-memory per-client limiter for the loopback/single-process service."""

    def __init__(self, requests_per_minute: int):
        self.limit = requests_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client_id: str, *, now: float | None = None) -> bool:
        """Return whether the client remains below the configured minute window."""
        current = time.monotonic() if now is None else now
        with self._lock:
            window = self._requests[client_id]
            while window and current - window[0] >= 60:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(current)
            return True


class InsightsHttpServer(ThreadingHTTPServer):
    """Threading server carrying immutable application configuration."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[SimpleHTTPRequestHandler],
        *,
        project_root: Path,
        service: InsightService,
        allowed_hosts: set[str],
    ):
        super().__init__(server_address, handler)
        self.project_root = project_root.resolve()
        self.static_roots = (
            (self.project_root / "web").resolve(),
            (self.project_root / "data" / "curated" / "dashboard_payloads").resolve(),
        )
        self.insight_service = service
        self.allowed_hosts = {host.casefold() for host in allowed_hosts}
        limits = service.settings.insights
        self.request_size_limit = limits.request_size_limit_bytes
        self.insight_semaphore = threading.BoundedSemaphore(limits.max_concurrent_requests)
        self.rate_limiter = SlidingWindowRateLimiter(limits.rate_limit_requests_per_minute)


class InsightsRequestHandler(SimpleHTTPRequestHandler):
    """Serve approved static roots and only the two narrowly scoped insights routes."""

    server: InsightsHttpServer

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(kwargs.pop("directory")), **kwargs)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Avoid logging paths, request bodies, document text, or custom queries."""
        return

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _host_allowed(self) -> bool:
        host_header = self.headers.get("Host", "")
        try:
            hostname = urlsplit(f"//{host_header}").hostname
        except ValueError:
            return False
        return bool(hostname and hostname.casefold() in self.server.allowed_hosts)

    def _write_json(self, status: HTTPStatus, payload: object) -> None:
        if hasattr(payload, "model_dump_json"):
            content = payload.model_dump_json().encode("utf-8")
        else:
            content = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _static_path_allowed(self, route: str) -> bool:
        """Allow only browser assets and aggregate dashboard payloads."""
        try:
            decoded = unquote(route, errors="strict")
            candidate = (self.server.project_root / decoded.lstrip("/\\")).resolve()
        except (OSError, RuntimeError, UnicodeError, ValueError):
            return False
        return any(
            candidate == static_root or candidate.is_relative_to(static_root)
            for static_root in self.server.static_roots
        )

    def _redirect_to_web(self) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", "/web/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _request_error(self, status: HTTPStatus, message: str) -> None:
        request_id = str(uuid.uuid4())
        response = InsightResponse(
            status=InsightStatus.INVALID_REQUEST,
            limitations=(message,),
            ai_metadata=InsightAiMetadata(
                model=None,
                prompt_version=PROMPT_VERSION,
                request_id=request_id,
            ),
        )
        self._write_json(status, response)

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._request_error(HTTPStatus.BAD_REQUEST, "The request host is not allowed.")
            return
        route = urlsplit(self.path).path
        if route == "/api/insights/health":
            self._write_json(HTTPStatus.OK, self.server.insight_service.health())
            return
        if route.startswith("/api/"):
            self._request_error(HTTPStatus.NOT_FOUND, "The requested API route does not exist.")
            return
        if route == "/":
            self._redirect_to_web()
            return
        if not self._static_path_allowed(route):
            self._request_error(
                HTTPStatus.NOT_FOUND, "The requested static resource is unavailable."
            )
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._request_error(HTTPStatus.BAD_REQUEST, "The request host is not allowed.")
            return
        route = urlsplit(self.path).path
        if route == "/":
            self._redirect_to_web()
            return
        if route.startswith("/api/") or not self._static_path_allowed(route):
            self._request_error(HTTPStatus.NOT_FOUND, "The requested resource is unavailable.")
            return
        super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._request_error(HTTPStatus.BAD_REQUEST, "The request host is not allowed.")
            return
        if urlsplit(self.path).path != "/api/insights":
            self._request_error(HTTPStatus.NOT_FOUND, "The requested API route does not exist.")
            return
        if not self.server.rate_limiter.allow(self.client_address[0]):
            self._request_error(HTTPStatus.TOO_MANY_REQUESTS, "Too many insight requests.")
            return
        if not self.server.insight_semaphore.acquire(blocking=False):
            self._request_error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "The insights service is at its concurrency limit. Try again later.",
            )
            return
        try:
            self._handle_insight_post()
        finally:
            self.server.insight_semaphore.release()

    def _handle_insight_post(self) -> None:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type != "application/json":
            self._request_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "JSON content is required.")
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._request_error(HTTPStatus.BAD_REQUEST, "Invalid request length.")
            return
        if content_length <= 0 or content_length > self.server.request_size_limit:
            self._request_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request size is invalid.")
            return
        body = self.rfile.read(content_length)
        try:
            raw = json.loads(body)
            request = InsightRequest.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, UnicodeDecodeError):
            self._request_error(HTTPStatus.BAD_REQUEST, "The insight request schema is invalid.")
            return
        response = self.server.insight_service.answer(request)
        status = {
            InsightStatus.ANSWERED: HTTPStatus.OK,
            InsightStatus.INSUFFICIENT_EVIDENCE: HTTPStatus.OK,
            InsightStatus.UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
            InsightStatus.INVALID_REQUEST: HTTPStatus.BAD_REQUEST,
            InsightStatus.UPSTREAM_ERROR: HTTPStatus.BAD_GATEWAY,
        }[response.status]
        self._write_json(status, response)


def create_insights_server(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    allowed_hosts: tuple[str, ...] = (),
    service: InsightService | None = None,
) -> InsightsHttpServer:
    """Create the same-origin static/insights server without starting it."""
    root = project_root.resolve()
    application = service or InsightService(root)
    hosts = {host, "127.0.0.1", "localhost", "::1", *allowed_hosts}

    class RootedHandler(InsightsRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=root, **kwargs)

    return InsightsHttpServer(
        (host, port),
        RootedHandler,
        project_root=root,
        service=application,
        allowed_hosts=hosts,
    )
