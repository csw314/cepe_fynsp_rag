"""Transport, validation, redaction, and fallback tests for the AskSage boundary."""

from __future__ import annotations

import logging
from typing import Any

import pytest
import requests

from cepe_fynsp.asksage.client import (
    AskSageClient,
    AskSageConfig,
    AskSageConfigurationError,
    AskSageResponseError,
    AskSageUnavailableError,
)


class FakeResponse:
    def __init__(
        self,
        payload: object = None,
        *,
        status_code: int = 200,
        content_type: str = "application/json",
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.error = error

    def json(self) -> object:
        if self.error:
            raise self.error
        return self.payload


class FakeSession:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []
        self.mounted: list[str] = []

    def mount(self, prefix: str, adapter: object) -> None:
        self.mounted.append(prefix)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, FakeResponse)
        return outcome


def _config(**overrides: Any) -> AskSageConfig:
    values = {
        "instance": "approved.example",
        "email": "synthetic@example.test",
        "api_key": "test-secret-key",
        "access_token": None,
        "model": "synthetic-model",
        "approved_hosts": ("api.approved.example",),
    }
    values.update(overrides)
    return AskSageConfig(**values)


def test_rejects_unapproved_host() -> None:
    config = _config(approved_hosts=("api.different.example",))
    with pytest.raises(AskSageConfigurationError, match="approved organizational instance"):
        _ = config.server_base_url


def test_rejects_instance_with_path_component() -> None:
    config = _config(instance="approved.example/unexpected")
    with pytest.raises(AskSageConfigurationError, match="must be a hostname"):
        _ = config.server_base_url


def test_environment_instance_is_not_implicitly_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASKSAGE_INSTANCE", "unapproved.example")
    monkeypatch.delenv("ASKSAGE_APPROVED_HOSTS", raising=False)
    client = AskSageClient.from_env()
    with pytest.raises(AskSageConfigurationError, match="approved organizational instance"):
        _ = client.config.server_base_url


def test_timeout_uses_unavailable_fallback_and_redacts_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = FakeSession([requests.Timeout("contains test-secret-key")])
    client = AskSageClient(_config(access_token="test-token"), session=session)  # type: ignore[arg-type]
    with caplog.at_level(logging.INFO):
        result = client.safe_chat_completion([{"role": "user", "content": "sensitive prompt"}])
    assert result["status"] == "unavailable"
    assert result["error_type"] == "AskSageUnavailableError"
    assert "test-secret-key" not in caplog.text
    assert "sensitive prompt" not in caplog.text


def test_retryable_http_status_maps_to_unavailable() -> None:
    client = AskSageClient(
        _config(access_token="test-token"),
        session=FakeSession([FakeResponse({}, status_code=503)]),  # type: ignore[arg-type]
    )
    with pytest.raises(AskSageUnavailableError, match="503"):
        client.chat_completion([])


def test_non_retryable_http_status_maps_to_response_error() -> None:
    client = AskSageClient(
        _config(access_token="test-token"),
        session=FakeSession([FakeResponse({}, status_code=400)]),  # type: ignore[arg-type]
    )
    with pytest.raises(AskSageResponseError, match="400"):
        client.chat_completion([])


def test_invalid_json_is_rejected_without_body_disclosure() -> None:
    error = requests.JSONDecodeError("invalid", "not-json", 0)
    client = AskSageClient(
        _config(access_token="test-token"),
        session=FakeSession([FakeResponse(error=error)]),  # type: ignore[arg-type]
    )
    with pytest.raises(AskSageResponseError, match="invalid JSON") as exc_info:
        client.chat_completion([])
    assert "not-json" not in str(exc_info.value)


def test_unexpected_response_schema_is_rejected() -> None:
    client = AskSageClient(
        _config(access_token="test-token"),
        session=FakeSession([FakeResponse({"unexpected": []})]),  # type: ignore[arg-type]
    )
    with pytest.raises(AskSageResponseError, match="unexpected response schema"):
        client.chat_completion([])


def test_token_exchange_is_cached_and_used_as_bearer() -> None:
    session = FakeSession(
        [
            FakeResponse({"access_token": "short-lived-token", "expires_in": 600}),
            FakeResponse({"choices": [{"message": {"content": "bounded answer"}}]}),
            FakeResponse({"choices": [{"message": {"content": "bounded answer"}}]}),
        ]
    )
    client = AskSageClient(_config(), session=session)  # type: ignore[arg-type]
    client.chat_completion([{"role": "user", "content": "first"}])
    client.chat_completion([{"role": "user", "content": "second"}])
    token_calls = [call for call in session.calls if call["url"].endswith("get-token-with-api-key")]
    chat_calls = [call for call in session.calls if call["url"].endswith("chat/completions")]
    assert len(token_calls) == 1
    assert len(chat_calls) == 2
    assert all(
        call["headers"]["Authorization"] == "Bearer short-lived-token" for call in chat_calls
    )
