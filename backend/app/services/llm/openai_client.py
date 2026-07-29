"""OpenAI provider — fallback reasoning engine and embeddings host."""

import json
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        api_key = settings.secret(settings.openai_api_key)
        self._model = settings.openai_model
        self._client = (
            AsyncOpenAI(api_key=api_key, timeout=settings.llm_timeout_seconds, max_retries=2)
            if api_key
            else None
        )

    @property
    def configured(self) -> bool:
        return self._client is not None

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
        effort: str = "medium",
        cacheable_system: bool = True,
    ) -> dict[str, Any]:
        if self._client is None:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured.")
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "result", "schema": schema, "strict": True},
                },
            )
        except RateLimitError as exc:
            raise ProviderUnavailable("OpenAI is rate limited; try again shortly.") from exc
        except (APIConnectionError, APIStatusError) as exc:
            logger.warning("openai_request_failed", error=str(exc))
            raise ProviderUnavailable("OpenAI could not be reached.") from exc

        content = response.choices[0].message.content or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailable("OpenAI returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise ProviderUnavailable("OpenAI returned a non-object JSON payload.")
        return parsed

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        effort: str = "medium",
        cacheable_system: bool = True,
    ) -> str:
        if self._client is None:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured.")
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except RateLimitError as exc:
            raise ProviderUnavailable("OpenAI is rate limited; try again shortly.") from exc
        except (APIConnectionError, APIStatusError) as exc:
            logger.warning("openai_request_failed", error=str(exc))
            raise ProviderUnavailable("OpenAI could not be reached.") from exc
        return response.choices[0].message.content or ""
