"""Hardened AskSage API boundary with optional, unavailable-safe behavior."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)


class AskSageError(RuntimeError):
    """Base exception that never includes credentials, prompts, or response bodies."""


class AskSageConfigurationError(AskSageError):
    """Unsafe or incomplete connection configuration."""


class AskSageUnavailableError(AskSageError):
    """Timeout, transport, or retry-exhaustion failure."""


class AskSageResponseError(AskSageError):
    """Unexpected HTTP, content type, JSON, or response schema."""


@dataclass(frozen=True)
class AskSageConfig:
    """Environment-provided AskSage connection settings."""

    instance: str
    email: str | None
    api_key: str | None
    access_token: str | None
    model: str
    approved_hosts: tuple[str, ...] = ("api.asksage.ai",)
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 60.0
    max_retries: int = 3
    backoff_factor: float = 0.5

    @property
    def api_host(self) -> str:
        """Return the documented instance-specific API host."""
        instance = self.instance.strip().removeprefix("https://").removeprefix("http://").strip("/")
        if not instance or any(character in instance for character in "/?#@"):
            raise AskSageConfigurationError(
                "ASKSAGE_INSTANCE must be a hostname, not a URL path or credential-bearing value."
            )
        return instance if instance.startswith("api.") else f"api.{instance}"

    def _base_url(self, surface: str) -> str:
        url = f"https://{self.api_host}/{surface}"
        host = urlparse(url).hostname
        if host is None or host.casefold() not in {
            value.casefold() for value in self.approved_hosts
        }:
            raise AskSageConfigurationError(
                "AskSage host is not in ASKSAGE_APPROVED_HOSTS; use the approved organizational instance."
            )
        return url

    @property
    def user_base_url(self) -> str:
        """Return the approved User API base URL."""
        return self._base_url("user")

    @property
    def server_base_url(self) -> str:
        """Return the approved Server API base URL."""
        return self._base_url("server")

    @property
    def openai_base_url(self) -> str:
        """Return the approved OpenAI-compatible base URL."""
        return f"{self.server_base_url}/openai/v1"

    @property
    def timeout(self) -> tuple[float, float]:
        """Return explicit connect/read timeouts for requests."""
        return (self.connect_timeout_seconds, self.read_timeout_seconds)


class AskSageClient:
    """Reusable, retrying requests client that logs metadata only."""

    def __init__(self, config: AskSageConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        retry = Retry(
            total=config.max_retries,
            connect=config.max_retries,
            read=config.max_retries,
            status=config.max_retries,
            allowed_methods=frozenset({"POST"}),
            status_forcelist=(408, 425, 429, 500, 502, 503, 504),
            backoff_factor=config.backoff_factor,
            backoff_jitter=0.25,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self._cached_token: str | None = config.access_token
        self._token_expires_at = float("inf") if config.access_token else 0.0

    @classmethod
    def from_env(cls) -> AskSageClient:
        """Create a client solely from environment configuration."""
        instance = os.getenv("ASKSAGE_INSTANCE", "asksage.ai")
        approved = tuple(
            value.strip()
            for value in os.getenv("ASKSAGE_APPROVED_HOSTS", "api.asksage.ai").split(",")
            if value.strip()
        )
        return cls(
            AskSageConfig(
                instance=instance,
                email=os.getenv("ASKSAGE_EMAIL"),
                api_key=os.getenv("ASKSAGE_API_KEY"),
                access_token=os.getenv("ASKSAGE_ACCESS_TOKEN"),
                model=os.getenv("ASKSAGE_MODEL", "gpt-4.1-mini"),
                approved_hosts=approved,
                connect_timeout_seconds=float(os.getenv("ASKSAGE_CONNECT_TIMEOUT_SECONDS", "10")),
                read_timeout_seconds=float(os.getenv("ASKSAGE_READ_TIMEOUT_SECONDS", "60")),
                max_retries=int(os.getenv("ASKSAGE_MAX_RETRIES", "3")),
                backoff_factor=float(os.getenv("ASKSAGE_BACKOFF_FACTOR", "0.5")),
            )
        )

    def _post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, Any],
        required_keys: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Send a redacted JSON request and validate the response envelope."""
        request_id = str(uuid.uuid4())
        safe_headers = {**headers, "X-Request-ID": request_id, "Accept": "application/json"}
        LOGGER.info(
            "AskSage request started request_id=%s endpoint=%s", request_id, urlparse(url).path
        )
        try:
            response = self.session.post(
                url,
                headers=safe_headers,
                json=body,
                timeout=self.config.timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            LOGGER.warning(
                "AskSage unavailable request_id=%s error_type=%s", request_id, type(exc).__name__
            )
            raise AskSageUnavailableError(
                f"AskSage request unavailable (request_id={request_id})."
            ) from exc
        except requests.RequestException as exc:
            raise AskSageResponseError(
                f"AskSage request failed (request_id={request_id})."
            ) from exc
        if response.status_code >= 500 or response.status_code in {408, 425, 429}:
            raise AskSageUnavailableError(
                f"AskSage service unavailable with HTTP {response.status_code} (request_id={request_id})."
            )
        if response.status_code >= 400:
            raise AskSageResponseError(
                f"AskSage rejected the request with HTTP {response.status_code} (request_id={request_id})."
            )
        content_type = response.headers.get("Content-Type", "").casefold()
        if "application/json" not in content_type:
            raise AskSageResponseError(
                f"AskSage returned an unexpected content type (request_id={request_id})."
            )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise AskSageResponseError(
                f"AskSage returned invalid JSON (request_id={request_id})."
            ) from exc
        if not isinstance(payload, dict) or any(key not in payload for key in required_keys):
            raise AskSageResponseError(
                f"AskSage returned an unexpected response schema (request_id={request_id})."
            )
        LOGGER.info("AskSage request completed request_id=%s", request_id)
        return payload

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return a cached token or exchange email/API key through the User API."""
        if not force_refresh and self._cached_token and time.time() < self._token_expires_at - 30:
            return self._cached_token
        if not self.config.email or not self.config.api_key:
            raise AskSageConfigurationError(
                "ASKSAGE_EMAIL and ASKSAGE_API_KEY are required for token exchange."
            )
        payload = self._post_json(
            f"{self.config.user_base_url}/get-token-with-api-key",
            headers={"Content-Type": "application/json"},
            body={"email": self.config.email, "api_key": self.config.api_key},
        )
        token = payload.get("access_token") or payload.get("token")
        if not isinstance(token, str) or not token:
            raise AskSageResponseError("AskSage token response did not contain a usable token.")
        expires_in = payload.get("expires_in", 900)
        try:
            lifetime = max(float(expires_in), 60.0)
        except (TypeError, ValueError):
            lifetime = 900.0
        self._cached_token = token
        self._token_expires_at = time.time() + lifetime
        return token

    def chat_completion(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Call the documented OpenAI-compatible chat-completions endpoint."""
        token = self.config.access_token or self.get_access_token()
        body: dict[str, Any] = {
            "model": kwargs.pop("model", self.config.model),
            "messages": messages,
            **kwargs,
        }
        payload = self._post_json(
            f"{self.config.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            body=body,
            required_keys=("choices",),
        )
        choices = payload.get("choices")
        if not isinstance(choices, list):
            raise AskSageResponseError("AskSage chat response choices are invalid.")
        return payload

    def query(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Call the documented Server API query endpoint with a cached access token."""
        token = self.config.access_token or self.get_access_token()
        return self._post_json(
            f"{self.config.server_base_url}/query",
            headers={"x-access-tokens": token, "Content-Type": "application/json"},
            body={"message": prompt, **kwargs},
        )

    def safe_chat_completion(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Return a deterministic unavailable state instead of blocking dashboard/report use."""
        try:
            return {"status": "available", "response": self.chat_completion(messages, **kwargs)}
        except AskSageError as exc:
            return {
                "status": "unavailable",
                "response": None,
                "message": "AI-generated narrative is unavailable; deterministic evidence remains available.",
                "error_type": type(exc).__name__,
            }
