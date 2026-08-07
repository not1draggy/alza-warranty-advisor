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
from app.agents.verification import verify_narrative
from app.core.errors import ProviderUnavailable
from app.core.logging import get_logger
from app.core.text import YEARS, counted
from app.schemas.common import ConfidenceBand, Verdict
from app.services.llm.base import LLMProvider

logger = get_logger(__name__)

# Verdicts that describe why there is no analysis, so there is nothing to reword.
_NO_ANALYSIS = frozenset({Verdict.INSUFFICIENT_EVIDENCE, Verdict.SERVICE_UNAVAILABLE})

_HEADLINES: dict[Verdict, str] = {
    Verdict.RECOMMENDED: "Oplatí sa — opravy zvyčajne stoja viac",
    Verdict.NEUTRAL: "Tesné — záleží na tom, koľko rizika znesiete",
    Verdict.NOT_RECOMMENDED: "Skôr sa neoplatí — opravy bývajú lacnejšie",
    Verdict.INSUFFICIENT_EVIDENCE: "Nemáme dosť podkladov na jednoznačnú odpoveď",
    Verdict.SERVICE_UNAVAILABLE: "Analýzu sa teraz nedá spustiť",
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
        if verdict in _NO_ANALYSIS:
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
        if not narrative.summary.strip():
            return fallback

        # The headline is never taken from the model: it is derived from the
        # decision, so the wording cannot contradict the recommendation.
        narrative.headline = _HEADLINES[verdict]
        if not narrative.reasons:
            narrative.reasons = fallback.reasons

        # Every figure in the wording must be one the pipeline computed.
        check = verify_narrative(
            " ".join([narrative.summary, *narrative.reasons]),
            economics=economics,
            failure_modes=failure_modes,
            confidence=confidence.score,
        )
        if not check.ok:
            logger.warning("composer_rejected_unsupported_figures", figures=check.unsupported)
            return fallback
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

    if verdict is Verdict.SERVICE_UNAVAILABLE:
        return ComposedNarrative(
            headline=headline,
            summary=(
                "Analýza sa nedokončila, pretože jazykový model neodpovedal. "
                "Nie je to tým, že by o tomto produkte neboli informácie — služba "
                "je nesprávne nastavená alebo dočasne nedostupná. Skúste to znova "
                "o chvíľu; ak to trvá, ide o nastavenie API kľúča."
            ),
            reasons=reasons,
        )

    if verdict is Verdict.INSUFFICIENT_EVIDENCE:
        summary = (
            f"Pre {identity.display_name} sme nenašli dôveryhodné verejné informácie "
            f"o cenách opráv, a hádať nebudeme. Pred rozhodnutím sa predajcu opýtajte, "
            f"koľko pri tomto modeli zvyčajne stojí oprava po záruke."
        )
        return ComposedNarrative(
            headline=headline,
            summary=summary,
            reasons=reasons or ["Nenašli sme použiteľné údaje o opravách."],
        )

    top = failure_modes[0] if failure_modes else None
    likely = (
        f"Najpravdepodobnejšia porucha je {top.name.lower()}, ktorej oprava stojí "
        f"zvyčajne okolo {top.cost.typical:.0f} {currency}. "
        if top
        else ""
    )
    summary = (
        f"Za {counted(years, *YEARS)} od skončenia výrobcovej záruky je "
        f"približne {economics.failure_probability * 100:.0f}% šanca, že "
        f"{identity.display_name} bude potrebovať opravu. {likely}"
        f"Oproti cene predĺženia {economics.warranty_price:.0f} {currency} vychádzajú "
        f"očakávané výdavky na opravy asi na {economics.expected_repair_cost:.0f} {currency}."
    )
    if confidence.band is ConfidenceBand.LOW:
        summary += " Verejných údajov o tomto modeli je málo, berte preto čísla ako orientačné."

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
