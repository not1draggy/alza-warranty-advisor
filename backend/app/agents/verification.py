"""Numeric verification of composed narratives.

The composer is told never to introduce a figure of its own, but "told" is not
"prevented". This module checks the wording against the analysis it was given:
every monetary amount and every percentage in the text must correspond to a value
the pipeline actually computed. Anything else means the sentence is describing a
different product than the one we measured, and the narrative is rejected.

Only figures attached to a currency or a percent sign are checked. Bare integers
("2 sources", "3 years") are not claims about money or risk, so verifying them
would produce false rejections without adding safety.
"""

import re
from dataclasses import dataclass

from app.agents.risk import Economics
from app.agents.types import ExtractedFailureMode

# 280 EUR · €280 · 280.50 EUR · 1,280 EUR
_AMOUNT_AFTER = re.compile(
    # `\b` binds only to the letter codes: it would never match after "%" or "€".
    r"(\d[\d,.]*)\s*(?:%|€|£|\$|(?:EUR|CZK|USD|GBP|PLN|HUF|SKK)\b)",
    re.IGNORECASE,
)
_AMOUNT_BEFORE = re.compile(r"(?:€|£|\$)\s*(\d[\d,.]*)")

# Money is rounded to whole units for display, so allow a unit of slack either way.
MONEY_TOLERANCE = 1.5
# Percentages are shown to the nearest whole point.
PERCENT_TOLERANCE = 1.5


@dataclass(slots=True)
class VerificationResult:
    ok: bool
    unsupported: list[float]


def allowed_values(
    economics: Economics, failure_modes: list[ExtractedFailureMode], *, confidence: float
) -> set[float]:
    """Every number the narrative is permitted to state."""
    values: set[float] = {
        economics.warranty_price,
        economics.expected_repair_cost,
        economics.average_repair_cost,
        economics.worst_case_repair_cost,
        abs(economics.net_value),
        economics.failure_probability * 100,
        confidence * 100,
    }
    if economics.break_even_probability is not None:
        values.add(economics.break_even_probability * 100)

    for mode in failure_modes:
        values.update(
            {
                mode.cost.minimum,
                mode.cost.typical,
                mode.cost.maximum,
                mode.annual_probability * 100,
                economics.window_probabilities.get(mode.slug, 0.0) * 100,
            }
        )
    return {round(value, 2) for value in values}


def extract_claims(text: str) -> list[float]:
    """Pull out every figure the text states as money or as a percentage."""
    found: list[float] = []
    for pattern in (_AMOUNT_AFTER, _AMOUNT_BEFORE):
        for raw in pattern.findall(text):
            parsed = _to_float(raw)
            if parsed is not None:
                found.append(parsed)
    return found


def verify_narrative(
    text: str,
    *,
    economics: Economics,
    failure_modes: list[ExtractedFailureMode],
    confidence: float,
) -> VerificationResult:
    permitted = allowed_values(economics, failure_modes, confidence=confidence)
    unsupported = [claim for claim in extract_claims(text) if not _matches_any(claim, permitted)]
    return VerificationResult(ok=not unsupported, unsupported=unsupported)


def _matches_any(claim: float, permitted: set[float]) -> bool:
    for value in permitted:
        tolerance = PERCENT_TOLERANCE if value <= 100 else MONEY_TOLERANCE
        if abs(claim - value) <= tolerance:
            return True
    return False


def _to_float(raw: str) -> float | None:
    cleaned = raw.strip().rstrip(".,")
    # Thousands separators vary by locale; treat a trailing group of three as one.
    if ("," in cleaned and "." in cleaned) or re.fullmatch(r"\d{1,3}(,\d{3})+", cleaned):
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
