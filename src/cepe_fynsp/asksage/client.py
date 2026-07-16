"""AskSage API client wrapper.

Keep low-level HTTP behavior isolated in this module. Do not hardcode secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class AskSageConfig:
    """AskSage connection settings."""

    instance: str
    email: str | None
    api_key: str | None
    access_token: str | None
    model: str
    timeout_seconds: int = 60

    @property
    def user_base_url(self) -> str:
        return f"https://api.{self.instance}/user"

    @property
    def server_base_url(self) -> str:
        return f"https://api.{self.instance}/server"

    @property
    def openai_base_url(self) -> str:
        return f"https://api.{self.instance}/server/openai/v1"


class AskSageClient:
    """Small requests-based client for AskSage interactions."""

    def __init__(self, config: AskSageConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "AskSageClient":
        """Create a client from environment variables."""
        return cls(
            AskSageConfig(
                instance=os.getenv("ASKSAGE_INSTANCE", "asksage.ai"),
                email=os.getenv("ASKSAGE_EMAIL"),
                api_key=os.getenv("ASKSAGE_API_KEY"),
                access_token=os.getenv("ASKSAGE_ACCESS_TOKEN"),
                model=os.getenv("ASKSAGE_MODEL", "gpt-4.1-mini"),
            )
        )

    def get_access_token(self) -> str:
        """Exchange email/API key for an access token."""
        if not self.config.email or not self.config.api_key:
            raise ValueError("ASKSAGE_EMAIL and ASKSAGE_API_KEY are required for token exchange.")
        response = requests.post(
            f"{self.config.user_base_url}/get-token-with-api-key",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"email": self.config.email, "api_key": self.config.api_key},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token") or payload.get("token")
        if not token:
            raise RuntimeError(f"Token not found in AskSage response keys: {list(payload)}")
        return str(token)

    def chat_completion(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Call the OpenAI-compatible chat completions endpoint."""
        token = self.config.access_token or self.config.api_key
        if not token:
            raise ValueError("ASKSAGE_ACCESS_TOKEN or ASKSAGE_API_KEY is required.")
        body: dict[str, Any] = {
            "model": kwargs.pop("model", self.config.model),
            "messages": messages,
            **kwargs,
        }
        response = requests.post(
            f"{self.config.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def query(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Call the AskSage server query endpoint."""
        token = self.config.access_token or self.config.api_key
        if not token:
            raise ValueError("ASKSAGE_ACCESS_TOKEN or ASKSAGE_API_KEY is required.")
        body: dict[str, Any] = {"message": prompt, **kwargs}
        response = requests.post(
            f"{self.config.server_base_url}/query",
            headers={"x-access-tokens": token, "Content-Type": "application/json"},
            json=body,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
