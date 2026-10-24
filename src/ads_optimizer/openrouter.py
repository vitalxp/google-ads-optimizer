from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ads_optimizer.config import Settings as AppSettings
from ads_optimizer.envfile import ENV_PATH


class OpenRouterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_site_url: str = Field(
        default="http://localhost:8787",
        alias="OPENROUTER_SITE_URL",
    )
    openrouter_app_name: str = Field(
        default="Google Ads Optimizer",
        alias="OPENROUTER_APP_NAME",
    )
    openrouter_default_model: str = Field(
        default="anthropic/claude-sonnet-4.5",
        alias="OPENROUTER_DEFAULT_MODEL",
    )


# Fallback if OpenRouter models API is unreachable
CURATED_TOP20: list[dict[str, Any]] = [
    {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5",
        "context_length": 200000,
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
    },
    {
        "id": "openai/gpt-5",
        "name": "GPT-5",
        "context_length": 400000,
        "pricing": {"prompt": "0.00000125", "completion": "0.00001"},
    },
    {
        "id": "google/gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "context_length": 1000000,
        "pricing": {"prompt": "0.00000125", "completion": "0.00001"},
    },
    {
        "id": "anthropic/claude-opus-4.6",
        "name": "Claude Opus 4.6",
        "context_length": 200000,
        "pricing": {"prompt": "0.000015", "completion": "0.000075"},
    },
    {
        "id": "google/gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "context_length": 1000000,
        "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
    },
    {
        "id": "openai/gpt-4.1",
        "name": "GPT-4.1",
        "context_length": 1000000,
        "pricing": {"prompt": "0.000002", "completion": "0.000008"},
    },
    {
        "id": "deepseek/deepseek-chat-v3.1",
        "name": "DeepSeek V3.1",
        "context_length": 163840,
        "pricing": {"prompt": "0.00000027", "completion": "0.0000011"},
    },
    {
        "id": "x-ai/grok-4",
        "name": "Grok 4",
        "context_length": 256000,
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
    },
    {
        "id": "meta-llama/llama-4-maverick",
        "name": "Llama 4 Maverick",
        "context_length": 1000000,
        "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
    },
    {
        "id": "mistralai/mistral-large-2411",
        "name": "Mistral Large",
        "context_length": 128000,
        "pricing": {"prompt": "0.000002", "completion": "0.000006"},
    },
    {
        "id": "anthropic/claude-haiku-4.5",
        "name": "Claude Haiku 4.5",
        "context_length": 200000,
        "pricing": {"prompt": "0.000001", "completion": "0.000005"},
    },
    {
        "id": "openai/gpt-4o",
        "name": "GPT-4o",
        "context_length": 128000,
        "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
    },
    {
        "id": "openai/o3",
        "name": "o3",
        "context_length": 200000,
        "pricing": {"prompt": "0.00001", "completion": "0.00004"},
    },
    {
        "id": "google/gemini-2.0-flash-001",
        "name": "Gemini 2.0 Flash",
        "context_length": 1000000,
        "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
    },
    {
        "id": "qwen/qwen3-235b-a22b",
        "name": "Qwen3 235B",
        "context_length": 131072,
        "pricing": {"prompt": "0.0000002", "completion": "0.0000006"},
    },
    {
        "id": "deepseek/deepseek-r1",
        "name": "DeepSeek R1",
        "context_length": 64000,
        "pricing": {"prompt": "0.00000055", "completion": "0.00000219"},
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct",
        "name": "Llama 3.3 70B",
        "context_length": 131072,
        "pricing": {"prompt": "0.0000001", "completion": "0.00000032"},
    },
    {
        "id": "mistralai/mistral-small-3.1-24b-instruct",
        "name": "Mistral Small 3.1",
        "context_length": 128000,
        "pricing": {"prompt": "0.0000001", "completion": "0.0000003"},
    },
    {
        "id": "cohere/command-r-plus-08-2024",
        "name": "Command R+",
        "context_length": 128000,
        "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
    },
    {
        "id": "amazon/nova-pro-v1",
        "name": "Amazon Nova Pro",
        "context_length": 300000,
        "pricing": {"prompt": "0.0000008", "completion": "0.0000032"},
    },
]

# Back-compat alias
CURATED_TOP10 = CURATED_TOP20[:10]


class OpenRouterClient:
    def __init__(self, settings: OpenRouterSettings | None = None) -> None:
        self.settings = settings or OpenRouterSettings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.openrouter_api_key.strip())

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }
        key = self.settings.openrouter_api_key.strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def list_top_models(self, limit: int = 20) -> list[dict[str, Any]]:
        """Top models that support tools, ranked by OpenRouter popularity."""
        url = f"{self.settings.openrouter_base_url}/models"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    url,
                    headers=self._headers(),
                    params={"supported_parameters": "tools", "sort": "top-weekly"},
                )
                if resp.status_code != 200:
                    resp = client.get(
                        url,
                        headers=self._headers(),
                        params={"supported_parameters": "tools"},
                    )
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            return CURATED_TOP20[:limit]

        models = payload.get("data") or payload.get("models") or []
        ranked: list[dict[str, Any]] = []
        for m in models:
            mid = m.get("id") or ""
            if not mid:
                continue
            # Prefer text chat models; skip pure image/audio
            modality = (m.get("architecture") or {}).get("modality") or ""
            if modality and "text" not in str(modality):
                continue
            ranked.append(
                {
                    "id": mid,
                    "name": m.get("name") or mid,
                    "context_length": m.get("context_length"),
                    "pricing": m.get("pricing") or {},
                    "description": (m.get("description") or "")[:180],
                }
            )
            if len(ranked) >= limit:
                break

        return ranked or CURATED_TOP20[:limit]

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        tool_choice: str | None = None,
        disable_tools: bool = False,
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Add it to .env to enable AI Assistant."
            )
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if not disable_tools and tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        elif disable_tools:
            # Some models keep calling tools if the schema is still present.
            body["tool_choice"] = "none"

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.settings.openrouter_base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text[:800]}")
            return resp.json()


@lru_cache(maxsize=1)
def get_openrouter() -> OpenRouterClient:
    # Allow runtime env injection without restarting pydantic env cache oddly
    if "OPENROUTER_API_KEY" in os.environ:
        return OpenRouterClient()
    return OpenRouterClient()


def merge_app_openrouter_defaults(app_settings: AppSettings | None) -> OpenRouterSettings:
    _ = app_settings
    return OpenRouterSettings()
