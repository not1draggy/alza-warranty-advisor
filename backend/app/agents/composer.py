"""Response composer: the words the customer actually reads.

The composer never sees raw evidence and never produces numbers of its own — it is
handed the finished analysis and rewrites it in plain language. When no model is
available it falls back to a deterministic template built from the same numbers, so
the product still answers the question.
"""

from app.agents.confidence import ConfidenceReport
from app.agents.prompts import COMPOSER_SCHEMA, COMPOSER_SYSTEM
from app.agents.risk import Economics
from app.agents.types import ComposedNarrative, ExtractedFailureMode, ProductIdentity
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.schemas.common import ConfidenceBand, Verdict
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)

_HEADLINES: dict[Verdict, str] = {
    Verdict.RECOMMENDED: "Worth buying — repairs usually cost more",
    Verdict.NEUTRAL: "A close call — it depends on your risk appetite",
    Verdict.NOT_RECOMMENDED: "Probably not worth it — repairs are usually cheaper",
    Verdict.INSUFFICIENT_EVIDENCE: "Not enough information to give you a straight answer",
}


class ComposerAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def compose(
        self,
        *,
        identity: ProductIdentity,
        verdict: Verdict,
        reasons: list[str],
        economics: Economics,
        confidence: ConfidenceReport,
        failure_modes: list[ExtractedFailureMode],
        years: int,
    ) -> ComposedNarrative:
        fallback = build_fallback_narrative(
            identity=identity,
            verdict=verdict,
            reasons=reasons,
            economics=economics,
            confidence=confidence,
            failure_modes=failure_modes,
            years=years,
        )
        if verdict is Verdict.INSUFFICIENT_EVIDENCE:
            return fallback

        try:
            payload = await self._llm.complete_json(
                system=COMPOSER_SYSTEM,
                user=_render_analysis(
                    identity, verdict, reasons, economics, confidence, failure_modes, years
                ),
                schema=COMPOSER_SCHEMA,
                max_tokens=1500,
                effort="medium",
            )
        except ProviderUnavailable as exc:
            logger.warning("composer_unavailable", error=str(exc))
            return fallback

        narrative = ComposedNarrative.model_validate(payload)
        if not narrative.headline.strip() or not narrative.summary.strip():
            return fallback
        if not narrative.reasons:
            narrative.reasons = fallback.reasons
        return narrative


def build_fallback_narrative(
    *,
    identity: ProductIdentity,
    verdict: Verdict,
    reasons: list[str],
    economics: Economics,
    confidence: ConfidenceReport,
    failure_modes: list[ExtractedFailureMode],
    years: int,
) -> ComposedNarrative:
    currency = economics.currency
    headline = _HEADLINES[verdict]

    if verdict is Verdict.INSUFFICIENT_EVIDENCE:
        summary = (
            f"We could not find reliable public repair information for "
            f"{identity.display_name}, so we will not guess. Ask the retailer what a "
            f"typical out-of-warranty repair costs for this model before deciding."
        )
        return ComposedNarrative(
            headline=headline,
            summary=summary,
            reasons=reasons or ["No usable repair data was found."],
        )

    top = failure_modes[0] if failure_modes else None
    likely = (
        f"The most likely problem is {top.name.lower()}, which typically costs about "
        f"{top.cost.typical:.0f} {currency} to fix. "
        if top
        else ""
    )
    summary = (
        f"Over {years} year{'s' if years != 1 else ''} after the manufacturer's warranty ends, "
        f"there is roughly a {economics.failure_probability * 100:.0f}% chance "
        f"{identity.display_name} needs a repair. {likely}"
        f"Weighing that against the {economics.warranty_price:.0f} {currency} extension, "
        f"expected repair spending comes to about {economics.expected_repair_cost:.0f} {currency}."
    )
    if confidence.band is ConfidenceBand.LOW:
        summary += " Public data on this model is thin, so treat these figures as indicative."

    return ComposedNarrative(headline=headline, summary=summary, reasons=reasons[:4])


def _render_analysis(
    identity: ProductIdentity,
    verdict: Verdict,
    reasons: list[str],
    economics: Economics,
    confidence: ConfidenceReport,
    failure_modes: list[ExtractedFailureMode],
    years: int,
) -> str:
    modes = "\n".join(
        f"- {mode.name}: {economics.window_probabilities.get(mode.slug, 0.0) * 100:.0f}% over "
        f"{years} years, typical repair {mode.cost.typical:.0f} {economics.currency} "
        f"(range {mode.cost.minimum:.0f}-{mode.cost.maximum:.0f})"
        for mode in failure_modes
    )
    return (
        f"PRODUCT: {identity.display_name}\n"
        f"WARRANTY WINDOW: {years} years\n"
        f"WARRANTY PRICE: {economics.warranty_price:.0f} {economics.currency}\n"
        f"DECISION: {verdict.value}\n"
        f"CHANCE OF NEEDING A REPAIR: {economics.failure_probability * 100:.0f}%\n"
        f"EXPECTED REPAIR SPEND: {economics.expected_repair_cost:.0f} {economics.currency}\n"
        f"AVERAGE REPAIR WHEN IT HAPPENS: {economics.average_repair_cost:.0f} "
        f"{economics.currency}\n"
        f"WORST CASE REPAIR: {economics.worst_case_repair_cost:.0f} {economics.currency}\n"
        f"CONFIDENCE: {confidence.score:.2f} ({confidence.band.value})\n"
        f"FAILURE MODES:\n{modes or '- none identified'}\n"
        f"SUPPORTING POINTS:\n" + "\n".join(f"- {reason}" for reason in reasons) + "\n\n"
        "Write the customer-facing explanation."
    )
