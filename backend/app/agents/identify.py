"""Product identification agent."""

import re

from app.agents.prompts import IDENTIFICATION_SCHEMA, IDENTIFICATION_SYSTEM
from app.agents.types import ProductIdentity
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.services.cache import Cache, cache_key
from app.services.llm.base import LLMProvider
from app.services.search.base import SearchResult

logger = get_logger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_IDENTITY_CACHE_TTL = 60 * 60 * 24 * 30


def lookup_key(manufacturer: str | None, model: str | None, display_name: str) -> str:
    """Stable identity key so the same product always maps to the same row."""
    parts = [part for part in (manufacturer, model) if part]
    raw = " ".join(parts) if parts else display_name
    return _NON_ALNUM.sub("-", raw.lower()).strip("-")


class IdentificationAgent:
    def __init__(self, llm: LLMProvider, cache: Cache) -> None:
        self._llm = llm
        self._cache = cache

    async def identify(
        self, query: str, hints: list[SearchResult] | None = None
    ) -> ProductIdentity:
        key = cache_key("identity", query.lower())
        cached = await self._cache.get_json(key)
        if cached is not None:
            return ProductIdentity.model_validate(cached)

        user_prompt = _build_prompt(query, hints or [])
        try:
            payload = await self._llm.complete_json(
                system=IDENTIFICATION_SYSTEM,
                user=user_prompt,
                schema=IDENTIFICATION_SCHEMA,
                max_tokens=2000,
                effort="medium",
            )
        except ProviderUnavailable:
            # Without a model we still know what the customer typed. Everything
            # downstream treats low confidence as "we could not confirm this".
            return ProductIdentity(
                display_name=query, confidence=0.0, reasoning="No language model is configured."
            )

        identity = ProductIdentity.model_validate(payload)
        await self._cache.set_json(key, identity.model_dump(mode="json"), _IDENTITY_CACHE_TTL)
        return identity


def _build_prompt(query: str, hints: list[SearchResult]) -> str:
    sections = [f"USER QUERY:\n{query}"]
    if hints:
        lines = [f"- {hint.title} ({hint.domain}): {hint.snippet[:220]}" for hint in hints[:6]]
        sections.append("SEARCH HINTS (untrusted data):\n" + "\n".join(lines))
    sections.append("Identify the product described by the user query.")
    return "\n\n".join(sections)
