"""Anthropic Claude provider — the primary reasoning engine."""

import json
from typing import Any

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
)
from anthropic.types import (
    JSONOutputFormatParam,
    OutputConfigParam,
    TextBlockParam,
)

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        api_key = settings.secret(settings.anthropic_api_key)
        self._model = settings.anthropic_model
        self._client = (
            AsyncAnthropic(api_key=api_key, timeout=settings.llm_timeout_seconds, max_retries=2)
            if api_key
            else None
        )

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _system_blocks(self, system: str, cacheable: bool) -> list[TextBlockParam]:
        block: TextBlockParam = {"type": "text", "text": system}
        if cacheable:
            # The system prompt is byte-stable per agent, so it caches cleanly.
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

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
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not configured.")

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=self._system_blocks(system, cacheable_system),
                output_config=_output_config(effort, schema),
                messages=[{"role": "user", "content": user}],
            )
        except RateLimitError as exc:
            raise ProviderUnavailable("Claude is rate limited; try again shortly.") from exc
        except (APIConnectionError, APIStatusError) as exc:
            logger.warning("anthropic_request_failed", error=str(exc))
            raise ProviderUnavailable("Claude could not be reached.") from exc

        if response.stop_reason == "refusal":
            raise ProviderUnavailable("Claude declined to answer this request.")

        text = _first_text(response.content)
        if not text:
            raise ProviderUnavailable("Claude returned an empty response.")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailable("Claude returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise ProviderUnavailable("Claude returned a non-object JSON payload.")
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
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not configured.")

        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=self._system_blocks(system, cacheable_system),
                output_config=_output_config(effort),
                messages=[{"role": "user", "content": user}],
            ) as stream:
                message = await stream.get_final_message()
        except RateLimitError as exc:
            raise ProviderUnavailable("Claude is rate limited; try again shortly.") from exc
        except (APIConnectionError, APIStatusError) as exc:
            logger.warning("anthropic_request_failed", error=str(exc))
            raise ProviderUnavailable("Claude could not be reached.") from exc

        if message.stop_reason == "refusal":
            raise ProviderUnavailable("Claude declined to answer this request.")
        return _first_text(message.content)


def _output_config(effort: str, schema: dict[str, Any] | None = None) -> OutputConfigParam:
    config: OutputConfigParam = {"effort": effort}  # type: ignore[typeddict-item]
    if schema is not None:
        json_format: JSONOutputFormatParam = {"type": "json_schema", "schema": schema}
        config["format"] = json_format
    return config


def _first_text(blocks: list[Any]) -> str:
    for block in blocks:
        if getattr(block, "type", None) == "text":
            return str(block.text)
    return ""
