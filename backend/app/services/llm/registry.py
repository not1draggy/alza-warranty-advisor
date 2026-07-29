"""Provider selection with automatic failover."""

from typing import Any

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.services.llm.anthropic_client import AnthropicProvider
from app.services.llm.base import LLMProvider, UnavailableLLM
from app.services.llm.openai_client import OpenAIProvider

logger = get_logger(__name__)

_NO_PROVIDER = (
    "No language model is configured. Set ANTHROPIC_API_KEY (preferred) or OPENAI_API_KEY."
)


class LLMRouter(LLMProvider):
    """Tries providers in order and falls through on availability errors."""

    name = "router"

    def __init__(self, providers: list[LLMProvider]) -> None:
        self._providers = [p for p in providers if p.configured]
        self._fallback = UnavailableLLM(_NO_PROVIDER)

    @property
    def configured(self) -> bool:
        return bool(self._providers)

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    async def _dispatch(self, method: str, **kwargs: Any) -> Any:
        if not self._providers:
            return await getattr(self._fallback, method)(**kwargs)
        last_error: ProviderUnavailable | None = None
        for provider in self._providers:
            try:
                return await getattr(provider, method)(**kwargs)
            except ProviderUnavailable as exc:
                logger.warning("llm_provider_failed", provider=provider.name, error=str(exc))
                last_error = exc
        raise last_error or ProviderUnavailable(_NO_PROVIDER)

    async def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        return await self._dispatch("complete_json", **kwargs)

    async def complete_text(self, **kwargs: Any) -> str:
        return await self._dispatch("complete_text", **kwargs)


def build_llm_router(settings: Settings) -> LLMRouter:
    return LLMRouter([AnthropicProvider(settings), OpenAIProvider(settings)])
