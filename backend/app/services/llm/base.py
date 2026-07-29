"""LLM provider abstraction.

Providers return structured JSON validated against a schema. Any provider that is
not configured raises `ProviderUnavailable` so callers degrade explicitly rather
than fabricating content.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.core.errors import ProviderUnavailable


class LLMProvider(ABC):
    name: str = "unknown"

    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
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
        """Return a JSON object guaranteed to satisfy `schema`."""

    @abstractmethod
    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        effort: str = "medium",
        cacheable_system: bool = True,
    ) -> str:
        """Return a plain-text completion."""


class UnavailableLLM(LLMProvider):
    """Stand-in used when no provider credentials are present."""

    name = "unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    @property
    def configured(self) -> bool:
        return False

    async def complete_json(self, **_: Any) -> dict[str, Any]:
        raise ProviderUnavailable(self._reason)

    async def complete_text(self, **_: Any) -> str:
        raise ProviderUnavailable(self._reason)
