"""Confidence scoring.

Confidence answers "how much should the customer trust this number?" and is built
from five observable signals rather than asked of the language model:

  1. how many sources survived verification
  2. how many independent domains they came from
  3. the average quality of those sources
  4. how well the product itself was identified
  5. how much of the answer is sourced versus modelled
"""

from dataclasses import dataclass
from statistics import mean

from app.agents.types import ExtractedFailureMode
from app.schemas.common import ConfidenceBand, EvidenceLevel, ValueOrigin

MIN_SOURCES_FOR_FULL_CREDIT = 6
MIN_DOMAINS_FOR_FULL_CREDIT = 4


@dataclass(slots=True)
class SourceSignal:
    domain: str
    quality_score: float


@dataclass(slots=True)
class ConfidenceReport:
    score: float
    band: ConfidenceBand
    evidence_level: EvidenceLevel
    source_count: int
    independent_domains: int
    drivers: list[str]
    uncertainties: list[str]


def determine_evidence_level(
    failure_modes: list[ExtractedFailureMode], sources: list[SourceSignal]
) -> EvidenceLevel:
    if not sources or not failure_modes:
        return EvidenceLevel.NONE

    sourced_costs = sum(1 for mode in failure_modes if mode.cost.origin is ValueOrigin.SOURCED)
    sourced_probabilities = sum(
        1 for mode in failure_modes if mode.probability_origin is ValueOrigin.SOURCED
    )
    high_quality_domains = len({s.domain for s in sources if s.quality_score >= 0.7})

    if sourced_costs >= 2 and high_quality_domains >= 2 and sourced_probabilities >= 1:
        return EvidenceLevel.VERIFIED
    if sourced_costs >= 1 or high_quality_domains >= 1:
        return EvidenceLevel.PARTIAL
    return EvidenceLevel.MODELLED


def score_confidence(
    *,
    failure_modes: list[ExtractedFailureMode],
    sources: list[SourceSignal],
    identification_confidence: float,
) -> ConfidenceReport:
    evidence_level = determine_evidence_level(failure_modes, sources)
    domains = {source.domain for source in sources}
    source_count = len(sources)
    domain_count = len(domains)

    if evidence_level is EvidenceLevel.NONE:
        return ConfidenceReport(
            score=0.0,
            band=ConfidenceBand.LOW,
            evidence_level=evidence_level,
            source_count=source_count,
            independent_domains=domain_count,
            drivers=[],
            uncertainties=["No usable public information was found for this product."],
        )

    volume = min(1.0, source_count / MIN_SOURCES_FOR_FULL_CREDIT)
    independence = min(1.0, domain_count / MIN_DOMAINS_FOR_FULL_CREDIT)
    quality = mean(source.quality_score for source in sources) if sources else 0.0
    identification = max(0.0, min(1.0, identification_confidence))
    groundedness = _groundedness(failure_modes)

    score = (
        0.20 * volume
        + 0.20 * independence
        + 0.25 * quality
        + 0.15 * identification
        + 0.20 * groundedness
    )
    score = round(max(0.0, min(1.0, score)), 3)

    drivers: list[str] = []
    uncertainties: list[str] = []

    if source_count >= MIN_SOURCES_FOR_FULL_CREDIT:
        drivers.append(f"{source_count} independent sources were used.")
    else:
        uncertainties.append(
            f"Only {source_count} usable source{'s' if source_count != 1 else ''} were found."
        )

    if domain_count >= MIN_DOMAINS_FOR_FULL_CREDIT:
        drivers.append(f"Evidence spans {domain_count} different websites.")
    elif domain_count <= 1:
        uncertainties.append("All evidence comes from a single website.")

    if quality >= 0.7:
        drivers.append("Most sources are manufacturer or professional repair references.")
    elif quality < 0.5:
        uncertainties.append("Sources are mostly community discussions rather than official data.")

    if identification >= 0.8:
        drivers.append("The exact product model was identified with high certainty.")
    elif identification < 0.5:
        uncertainties.append("The exact product model could not be confirmed.")

    if groundedness >= 0.7:
        drivers.append("Repair prices come from cited sources rather than assumptions.")
    else:
        uncertainties.append("Some repair prices are modelled estimates, not published figures.")

    return ConfidenceReport(
        score=score,
        band=confidence_band(score),
        evidence_level=evidence_level,
        source_count=source_count,
        independent_domains=domain_count,
        drivers=drivers,
        uncertainties=uncertainties,
    )


def confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.7:
        return ConfidenceBand.HIGH
    if score >= 0.45:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def _groundedness(failure_modes: list[ExtractedFailureMode]) -> float:
    """Share of displayed values that trace back to a source rather than an assumption."""
    if not failure_modes:
        return 0.0
    total = len(failure_modes) * 2
    grounded = 0
    for mode in failure_modes:
        if mode.cost.origin is ValueOrigin.SOURCED:
            grounded += 1
        elif mode.cost.origin is ValueOrigin.DERIVED:
            grounded += 0.5
        if mode.probability_origin is ValueOrigin.SOURCED:
            grounded += 1
        elif mode.probability_origin is ValueOrigin.DERIVED:
            grounded += 0.5
    return grounded / total
