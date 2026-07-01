from __future__ import annotations

import json
import os
import textwrap
import urllib.error
import urllib.request
from typing import Protocol


class ProviderError(RuntimeError):
    """Raised when a model provider cannot produce a response."""


Message = dict[str, str]


class ModelProvider(Protocol):
    def generate(self, messages: list[Message], model: str, temperature: float = 0.2) -> str:
        """Return model output for the supplied chat messages."""


class MockProvider:
    """A deterministic provider that makes examples and tests run without API keys."""

    def generate(self, messages: list[Message], model: str, temperature: float = 0.2) -> str:
        user_message = next((item["content"] for item in reversed(messages) if item["role"] == "user"), "")
        compact_prompt = " ".join(user_message.split())
        if len(compact_prompt) > 700:
            compact_prompt = compact_prompt[:697] + "..."
        return textwrap.dedent(
            f"""\
            Mock agent output ({model})

            Intent:
            {compact_prompt}

            Suggested next action:
            Replace provider = "mock" with provider = "openai" and set OPENAI_API_KEY when you are ready to run the same runbook with a real model.
            """
        ).strip()


class OpenAICompatibleProvider:
    """Tiny OpenAI-compatible chat-completions client with no runtime dependency."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("AGENTRUNBOOK_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com").rstrip("/")

    def generate(self, messages: list[Message], model: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY or AGENTRUNBOOK_API_KEY is required for provider = 'openai'")

        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"model provider returned HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"model provider request failed: {exc}") from exc

        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected provider response: {data}") from exc


def make_provider(name: str) -> ModelProvider:
    normalized = name.strip().lower()
    if normalized in {"mock", "dry-run", "dryrun"}:
        return MockProvider()
    if normalized in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleProvider()
    raise ProviderError(f"unknown provider {name!r}; expected 'mock' or 'openai'")
