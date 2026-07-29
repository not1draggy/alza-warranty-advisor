"""Probability and cost mathematics.

Pure functions, no I/O. This is the module that decides what the customer is told,
so every formula is stated explicitly and covered by tests.

Model
-----
Each failure mode carries an annual probability `p`. Over an `n`-year window the
probability that the mode occurs at least once is `1 - (1 - p)^n`, assuming years
are independent. Modes are treated as independent of one another, which is the
conservative choice: correlated failures would raise the joint probability, so we
never overstate the case for the warranty by assuming independence.
"""

from dataclasses import dataclass

from app.agents.types import ExtractedFailureMode
from app.schemas.common import EvidenceLevel, RiskBand, Verdict

# Reference exposure used to normalise expected cost into a 0-1 risk term when the
# product price is unknown. Surfaced to the user as an assumption.
DEFAULT_COST_REFERENCE = 500.0

# Verdict thresholds on `expected_repair_cost / warranty_price`.
RECOMMEND_RATIO = 1.3
NEUTRAL_RATIO = 0.8

# Below this confidence a positive recommendation is softened to neutral.
MIN_CONFIDENCE_FOR_RECOMMENDATION = 0.35


def window_probability(annual_probability: float, years: int) -> float:
    """Probability that an event with annual rate `p` happens at least once in `years`."""
    p = _clamp(annual_probability, 0.0, 1.0)
    if years <= 0:
        return 0.0
    return _clamp(1.0 - (1.0 - p) ** years, 0.0, 1.0)


def combined_failure_probability(window_probabilities: list[float]) -> float:
    """Probability that at least one independent mode occurs."""
    survival = 1.0
    for probability in window_probabilities:
        survival *= 1.0 - _clamp(probability, 0.0, 1.0)
    return _clamp(1.0 - survival, 0.0, 1.0)


@dataclass(slots=True)
class TimelineEntry:
    year: int
    cumulative_failure_probability: float
    cumulative_expected_cost: float


@dataclass(slots=True)
class Economics:
    currency: str
    expected_repair_cost: float
    average_repair_cost: float
    worst_case_repair_cost: float
    failure_probability: float
    warranty_price: float
    net_value: float
    value_ratio: float
    break_even_probability: float | None
    window_probabilities: dict[str, float]
    timeline: list[TimelineEntry]


def compute_economics(
    failure_modes: list[ExtractedFailureMode],
    *,
    years: int,
    warranty_price: float,
    currency: str = "EUR",
) -> Economics:
    """Turn failure modes into the numbers shown to the customer."""
    window = {
        mode.slug: window_probability(mode.annual_probability, years) for mode in failure_modes
    }

    expected = sum(window[mode.slug] * mode.cost.typical for mode in failure_modes)
    failure_probability = combined_failure_probability(list(window.values()))
    worst_case = max((mode.cost.maximum for mode in failure_modes), default=0.0)

    # Expected spend conditional on something actually breaking.
    average = expected / failure_probability if failure_probability > 0 else 0.0

    net_value = expected - warranty_price
    value_ratio = expected / warranty_price if warranty_price > 0 else 0.0
    break_even = _clamp(warranty_price / average, 0.0, 1.0) if average > 0 else None

    timeline: list[TimelineEntry] = []
    for year in range(1, max(1, years) + 1):
        year_window = [window_probability(mode.annual_probability, year) for mode in failure_modes]
        cumulative_cost = sum(
            probability * mode.cost.typical
            for probability, mode in zip(year_window, failure_modes, strict=True)
        )
        timeline.append(
            TimelineEntry(
                year=year,
                cumulative_failure_probability=round(combined_failure_probability(year_window), 4),
                cumulative_expected_cost=round(cumulative_cost, 2),
            )
        )

    return Economics(
        currency=currency,
        expected_repair_cost=round(expected, 2),
        average_repair_cost=round(average, 2),
        worst_case_repair_cost=round(worst_case, 2),
        failure_probability=round(failure_probability, 4),
        warranty_price=round(warranty_price, 2),
        net_value=round(net_value, 2),
        value_ratio=round(value_ratio, 3),
        break_even_probability=round(break_even, 4) if break_even is not None else None,
        window_probabilities={slug: round(value, 4) for slug, value in window.items()},
        timeline=timeline,
    )


def compute_risk_score(economics: Economics, *, product_price: float | None = None) -> float:
    """Ownership risk on a 0-100 scale: how likely, and how expensive, trouble is."""
    reference = product_price if product_price and product_price > 0 else DEFAULT_COST_REFERENCE
    likelihood = economics.failure_probability
    exposure = _clamp(economics.expected_repair_cost / reference, 0.0, 1.0)
    severity = _clamp(economics.worst_case_repair_cost / reference, 0.0, 1.0)
    score = 100.0 * (0.50 * likelihood + 0.30 * exposure + 0.20 * severity)
    return round(_clamp(score, 0.0, 100.0), 1)


def risk_band(score: float) -> RiskBand:
    if score < 25:
        return RiskBand.LOW
    if score < 50:
        return RiskBand.MODERATE
    if score < 75:
        return RiskBand.HIGH
    return RiskBand.SEVERE


def risk_drivers(
    economics: Economics, failure_modes: list[ExtractedFailureMode], *, limit: int = 3
) -> list[str]:
    """Human-readable explanation of what pushes the risk score up."""
    ranked = sorted(
        failure_modes,
        key=lambda mode: economics.window_probabilities.get(mode.slug, 0.0) * mode.cost.typical,
        reverse=True,
    )
    drivers = []
    for mode in ranked[:limit]:
        probability = economics.window_probabilities.get(mode.slug, 0.0)
        drivers.append(
            f"{mode.name}: {probability * 100:.0f}% šanca za dané obdobie, "
            f"zvyčajne {mode.cost.typical:.0f} {economics.currency}"
        )
    return drivers


def decide_verdict(
    economics: Economics,
    *,
    confidence: float,
    evidence_level: EvidenceLevel,
) -> tuple[Verdict, list[str]]:
    """Map economics plus evidence quality onto a recommendation."""
    reasons: list[str] = []

    if evidence_level is EvidenceLevel.NONE:
        return Verdict.INSUFFICIENT_EVIDENCE, [
            "Pre tento produkt sme nenašli dôveryhodné verejné informácie o opravách."
        ]

    if economics.warranty_price <= 0:
        return Verdict.RECOMMENDED, ["Predĺženie nič nestojí, takže nemá žiadnu nevýhodu."]

    ratio = economics.value_ratio
    if ratio >= RECOMMEND_RATIO:
        verdict = Verdict.RECOMMENDED
        reasons.append(
            f"Očakávané výdavky na opravy ({economics.expected_repair_cost:.0f} "
            f"{economics.currency}) sú približne {ratio:.1f}× vyššie ako cena predĺženia."
        )
    elif ratio >= NEUTRAL_RATIO:
        verdict = Verdict.NEUTRAL
        reasons.append(
            f"Očakávané výdavky na opravy ({economics.expected_repair_cost:.0f} "
            f"{economics.currency}) sú blízko cene predĺženia."
        )
    else:
        verdict = Verdict.NOT_RECOMMENDED
        reasons.append(
            f"Očakávané výdavky na opravy ({economics.expected_repair_cost:.0f} "
            f"{economics.currency}) sú výrazne nižšie ako cena predĺženia."
        )

    if economics.break_even_probability is not None:
        reasons.append(
            f"Predĺženie sa zaplatí, ak šanca na opravu presiahne "
            f"{economics.break_even_probability * 100:.0f}%; odhad je "
            f"{economics.failure_probability * 100:.0f}%."
        )

    if verdict is Verdict.RECOMMENDED and confidence < MIN_CONFIDENCE_FOR_RECOMMENDATION:
        reasons.append(
            "Podkladov je málo, preto to uvádzame ako vyrovnané rozhodnutie, "
            "nie ako jednoznačné odporúčanie."
        )
        verdict = Verdict.NEUTRAL

    if evidence_level is EvidenceLevel.MODELLED:
        reasons.append(
            "Nenašli sme ceny opráv priamo pre tento produkt; použili sme priemery "
            "za kategóriu a sú označené ako odhad."
        )

    return verdict, reasons


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
