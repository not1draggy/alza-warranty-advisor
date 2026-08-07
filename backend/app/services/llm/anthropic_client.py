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
from app.core.errors import ProviderReason, ProviderUnavailable
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
            raise ProviderUnavailable(
                "ANTHROPIC_API_KEY is not configured.",
                reason=ProviderReason.NOT_CONFIGURED,
            )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                system=self._system_blocks(system, cacheable_system),
                output_config=_output_config(effort, schema),
                messages=[{"role": "user", "content": user}],
            )
        except RateLimitError as exc:
            raise ProviderUnavailable(
                "Claude is rate limited; try again shortly.",
                reason=ProviderReason.RATE_LIMITED,
            ) from exc
        except APIStatusError as exc:
            logger.warning("anthropic_request_failed", status=exc.status_code, error=str(exc))
            raise _status_error(exc, self._model) from exc
        except APIConnectionError as exc:
            logger.warning("anthropic_unreachable", error=str(exc))
            raise ProviderUnavailable(
                "Claude could not be reached.", reason=ProviderReason.UNREACHABLE
            ) from exc

        if response.stop_reason == "refusal":
            raise ProviderUnavailable(
                "Claude declined to answer this request.",
                reason=ProviderReason.BAD_RESPONSE,
            )

        text = _first_text(response.content)
        if not text:
            raise ProviderUnavailable(
                "Claude returned an empty response.", reason=ProviderReason.BAD_RESPONSE
            )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailable(
                "Claude returned malformed JSON.", reason=ProviderReason.BAD_RESPONSE
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderUnavailable(
                "Claude returned a non-object JSON payload.", reason=ProviderReason.BAD_RESPONSE
            )
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
            raise ProviderUnavailable(
                "ANTHROPIC_API_KEY is not configured.",
                reason=ProviderReason.NOT_CONFIGURED,
            )

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
            raise ProviderUnavailable(
                "Claude is rate limited; try again shortly.",
                reason=ProviderReason.RATE_LIMITED,
            ) from exc
        except APIStatusError as exc:
            logger.warning("anthropic_request_failed", status=exc.status_code, error=str(exc))
            raise _status_error(exc, self._model) from exc
        except APIConnectionError as exc:
            logger.warning("anthropic_unreachable", error=str(exc))
            raise ProviderUnavailable(
                "Claude could not be reached.", reason=ProviderReason.UNREACHABLE
            ) from exc

        if message.stop_reason == "refusal":
            raise ProviderUnavailable(
                "Claude declined to answer this request.",
                reason=ProviderReason.BAD_RESPONSE,
            )
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


def _status_error(exc: APIStatusError, model: str) -> ProviderUnavailable:
    """Turn an HTTP status from the API into something an operator can act on.

    A rejected key, an unknown model name and an exhausted balance all arrive as
    plain HTTP errors. Reporting them as "could not be reached" sends whoever is
    debugging to the network when the fix is in the environment file.
    """
    status_code = exc.status_code
    if status_code in (401, 403):
        return ProviderUnavailable(
            "ANTHROPIC_API_KEY was rejected by the Anthropic API. Check that the key "
            "is complete, current, and belongs to an active account.",
            reason=ProviderReason.REJECTED_CREDENTIALS,
        )
    if status_code == 404:
        return ProviderUnavailable(
            f"The Anthropic API does not offer a model named '{model}' to this key. "
            "Set ANTHROPIC_MODEL to a model your account can use.",
            reason=ProviderReason.MODEL_UNAVAILABLE,
        )
    if status_code == 402:
        return ProviderUnavailable(
            "The Anthropic account has no remaining credit.",
            reason=ProviderReason.QUOTA_EXHAUSTED,
        )
    if status_code == 429:
        return ProviderUnavailable(
            "Claude is rate limited; try again shortly.",
            reason=ProviderReason.RATE_LIMITED,
        )
    return ProviderUnavailable(
        f"Claude returned HTTP {status_code}.", reason=ProviderReason.UNREACHABLE
    )
