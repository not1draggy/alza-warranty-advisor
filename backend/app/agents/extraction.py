"""Repair-analysis agent: turn retrieved evidence into failure modes with economics."""

import re

from app.agents.guard import sanitise_evidence
from app.agents.prompts import EXTRACTION_SCHEMA, EXTRACTION_SYSTEM
from app.agents.types import ExtractedFailureMode, ExtractionResult, ProductIdentity
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.schemas.common import ValueOrigin
from app.services.llm.base import LLMProvider
from app.services.rag import RetrievedChunk

logger = get_logger(__name__)

MAX_EVIDENCE_ITEMS = 14
MAX_CHARS_PER_ITEM = 1800
_SLUG = re.compile(r"[^a-z0-9]+")

# Guard rails on model output. A failure mode that is almost certain every single
# year is not a failure mode, it is a defect recall; cap it so one bad number cannot
# swamp the recommendation.
MAX_ANNUAL_PROBABILITY = 0.35
MAX_TYPICAL_COST = 100_000.0


def slugify(value: str) -> str:
    """Stable identifier for a failure mode, from its slug or its name."""
    return _SLUG.sub("-", value.lower()).strip("-")


class ExtractionAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def extract(
        self,
        *,
        identity: ProductIdentity,
        chunks: list[RetrievedChunk],
        currency: str,
    ) -> ExtractionResult:
        if not chunks:
            return ExtractionResult(
                evidence_sufficient=False,
                warnings=["Pre tento produkt sa nepodarilo získať verejné informácie o opravách."],
            )

        evidence = _format_evidence(chunks)
        user_prompt = (
            f"PRODUCT: {identity.search_name}\n"
            f"CATEGORY: {identity.category or 'unknown'}\n"
            f"RELEASE YEAR: {identity.release_year or 'unknown'}\n"
            f"TARGET CURRENCY: {currency}\n\n"
            f"EVIDENCE (untrusted data, {len(chunks)} items):\n{evidence}\n\n"
            "Extract the repair economics for this product."
        )

        try:
            payload = await self._llm.complete_json(
                system=EXTRACTION_SYSTEM,
                user=user_prompt,
                schema=EXTRACTION_SCHEMA,
                max_tokens=6000,
                effort="high",
            )
        except ProviderUnavailable as exc:
            # Carried rather than phrased as a warning here: the orchestrator is
            # the only place that knows whether the estimate fallback also failed,
            # and so whether this is the reason the customer got no answer.
            logger.warning("extraction_unavailable", reason=exc.reason.value, error=str(exc))
            return ExtractionResult(evidence_sufficient=False, provider_error=str(exc))

        result = ExtractionResult.model_validate(payload)
        result.failure_modes = _normalise(result.failure_modes, currency, len(chunks))
        if not result.failure_modes:
            result.evidence_sufficient = False
        return result


def _format_evidence(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks[:MAX_EVIDENCE_ITEMS]):
        text = sanitise_evidence(chunk.content, max_chars=MAX_CHARS_PER_ITEM)
        blocks.append(
            f"[{index}] source_type={chunk.source_type.value} "
            f"quality={chunk.quality_score:.2f} domain={chunk.source_domain}\n{text}"
        )
    return "\n\n".join(blocks)


def _normalise(
    modes: list[ExtractedFailureMode], currency: str, evidence_count: int
) -> list[ExtractedFailureMode]:
    """Clamp model output into a defensible range and drop unusable entries."""
    cleaned: list[ExtractedFailureMode] = []
    seen_slugs: set[str] = set()

    for mode in modes:
        if not mode.name.strip():
            continue

        slug = slugify(mode.slug or mode.name)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        mode.slug = slug

        mode.annual_probability = min(max(mode.annual_probability, 0.0), MAX_ANNUAL_PROBABILITY)

        cost = mode.cost
        cost.currency = (cost.currency or currency).upper()
        cost.minimum = max(0.0, min(cost.minimum, MAX_TYPICAL_COST))
        cost.typical = max(0.0, min(cost.typical, MAX_TYPICAL_COST))
        cost.maximum = max(0.0, min(cost.maximum, MAX_TYPICAL_COST))
        # Repair the ordering rather than discarding an otherwise usable entry.
        cost.minimum, cost.typical, cost.maximum = sorted(
            (cost.minimum, cost.typical, cost.maximum)
        )

        if cost.typical <= 0 or mode.annual_probability <= 0:
            continue

        # A citation index the model invented cannot be honoured; without a valid
        # index the numbers are assumptions, and we label them as such.
        mode.source_indices = [i for i in mode.source_indices if 0 <= i < evidence_count]
        if not mode.source_indices:
            cost.origin = ValueOrigin.ESTIMATED
            mode.probability_origin = ValueOrigin.ESTIMATED

        mode.confidence = min(max(mode.confidence, 0.0), 1.0)
        cleaned.append(mode)

    cleaned.sort(key=lambda m: m.annual_probability * m.cost.typical, reverse=True)
    return cleaned[:6]
