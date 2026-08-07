"""Last-resort estimate when no repair evidence could be retrieved.

The product's rule is never to invent a figure and present it as fact. This agent
does not break that rule, it takes the other honest option: it says plainly that
nothing was found for this model and offers what typically goes wrong with the
*class* of product instead.

Everything it produces is forced to `ValueOrigin.ESTIMATED`, drives the evidence
level to `MODELLED`, and is capped to a low confidence, so the interface labels it
as an estimate wherever it appears. It is a starting point for the customer, never
a quote.
"""

from app.agents.extraction import MAX_ANNUAL_PROBABILITY, MAX_TYPICAL_COST, slugify
from app.agents.prompts import ESTIMATION_SCHEMA, ESTIMATION_SYSTEM
from app.agents.types import CostEvidence, ExtractedFailureMode, ExtractionResult, ProductIdentity
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.schemas.common import ValueOrigin
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)

MAX_ESTIMATED_MODES = 5
# An estimate about a product class can never be as trustworthy as a cited price,
# so its per-entry confidence is held below the level a sourced value can reach.
MAX_ESTIMATED_CONFIDENCE = 0.45


class EstimationAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def estimate(self, *, identity: ProductIdentity, currency: str) -> ExtractionResult:
        prompt = (
            f"PRODUCT: {identity.search_name}\n"
            f"CATEGORY: {identity.category or 'unknown'}\n"
            f"RELEASE YEAR: {identity.release_year or 'unknown'}\n"
            f"TARGET CURRENCY: {currency}\n\n"
            "No public repair information could be retrieved for this product. "
            "Estimate the repair economics for its product class."
        )
        try:
            payload = await self._llm.complete_json(
                system=ESTIMATION_SYSTEM,
                user=prompt,
                schema=ESTIMATION_SCHEMA,
                max_tokens=3000,
                effort="high",
            )
        except ProviderUnavailable as exc:
            logger.warning("estimation_unavailable", reason=exc.reason.value, error=str(exc))
            return ExtractionResult(evidence_sufficient=False, provider_error=str(exc))

        modes = _to_failure_modes(payload.get("failure_modes", []), currency)
        if not modes:
            return ExtractionResult(evidence_sufficient=False)

        product_class = str(payload.get("product_class") or "").strip()
        basis = f" Vychádza z triedy produktu: {product_class}." if product_class else ""

        return ExtractionResult(
            failure_modes=modes,
            evidence_sufficient=True,
            assumptions=[
                "Pre tento model sme nenašli konkrétne verejné ceny opráv. Nasledujúce "
                "čísla sú všeobecný odhad pre podobné zariadenia, nie údaje o tomto "
                f"kuse.{basis}"
            ],
            warnings=[
                "Tento odhad nevychádza zo zdrojov o tomto modeli, ale zo všeobecných "
                "znalostí o podobných produktoch. Berte ho ako orientačný a cenu opravy "
                "si overte u predajcu alebo v servise."
            ],
        )


def _to_failure_modes(raw: list[dict], currency: str) -> list[ExtractedFailureMode]:
    """Clamp the model's answer and stamp every value as an estimate."""
    modes: list[ExtractedFailureMode] = []
    for item in raw:
        name = str(item.get("name") or "").strip()
        cost = item.get("cost") or {}
        typical = _positive(cost.get("typical"))
        probability = _positive(item.get("annual_probability"))
        if not name or typical is None or probability is None:
            continue

        minimum = _positive(cost.get("minimum")) or typical
        maximum = _positive(cost.get("maximum")) or typical
        # A model that returns an inverted range is describing the same two numbers.
        low, high = sorted((minimum, maximum))

        modes.append(
            ExtractedFailureMode(
                slug=str(item.get("slug") or "").strip() or slugify(name),
                name=name,
                component=item.get("component"),
                description=item.get("description"),
                annual_probability=min(probability, MAX_ANNUAL_PROBABILITY),
                # Nothing here traces to a source, and saying otherwise would be
                # the exact failure this agent exists to avoid.
                probability_origin=ValueOrigin.ESTIMATED,
                cost=CostEvidence(
                    currency=currency,
                    minimum=min(low, MAX_TYPICAL_COST),
                    typical=min(typical, MAX_TYPICAL_COST),
                    maximum=min(high, MAX_TYPICAL_COST),
                    origin=ValueOrigin.ESTIMATED,
                    note="Odhad pre triedu produktu, nie cena z konkrétneho zdroja.",
                ),
                repair_difficulty=item.get("repair_difficulty"),
                typical_repair_days=item.get("typical_repair_days"),
                confidence=min(_positive(item.get("confidence")) or 0.3, MAX_ESTIMATED_CONFIDENCE),
                source_indices=[],
            )
        )

    modes.sort(key=lambda mode: mode.annual_probability * mode.cost.typical, reverse=True)
    return modes[:MAX_ESTIMATED_MODES]


def _positive(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
