"""Deterministic source classification and quality scoring.

Quality drives two things: which evidence the extraction agent is allowed to see,
and how much confidence the final answer earns. Keeping it deterministic means the
same page always scores the same, and the reasoning is auditable.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.common import SourceType

# Weight applied to every fact taken from a source of this type.
TYPE_WEIGHT: dict[SourceType, float] = {
    SourceType.MANUFACTURER: 1.00,
    SourceType.AUTHORIZED_SERVICE: 0.95,
    SourceType.RELIABILITY_REPORT: 0.90,
    SourceType.PARTS_CATALOG: 0.85,
    SourceType.REPAIR_PROFESSIONAL: 0.80,
    SourceType.RETAILER: 0.55,
    SourceType.COMMUNITY: 0.45,
    SourceType.UNKNOWN: 0.30,
}

# Domains whose role is unambiguous. Suffix match, so subdomains are covered.
KNOWN_DOMAINS: dict[str, SourceType] = {
    # Manufacturers
    "samsung.com": SourceType.MANUFACTURER,
    "lg.com": SourceType.MANUFACTURER,
    "sony.com": SourceType.MANUFACTURER,
    "philips.com": SourceType.MANUFACTURER,
    "panasonic.com": SourceType.MANUFACTURER,
    "bosch-home.com": SourceType.MANUFACTURER,
    "siemens-home.com": SourceType.MANUFACTURER,
    "apple.com": SourceType.MANUFACTURER,
    "dell.com": SourceType.MANUFACTURER,
    "hp.com": SourceType.MANUFACTURER,
    "lenovo.com": SourceType.MANUFACTURER,
    "asus.com": SourceType.MANUFACTURER,
    "acer.com": SourceType.MANUFACTURER,
    "whirlpool.com": SourceType.MANUFACTURER,
    "electrolux.com": SourceType.MANUFACTURER,
    "miele.com": SourceType.MANUFACTURER,
    "tcl.com": SourceType.MANUFACTURER,
    "hisense.com": SourceType.MANUFACTURER,
    # Repair professionals and manuals
    "ifixit.com": SourceType.REPAIR_PROFESSIONAL,
    "repairclinic.com": SourceType.REPAIR_PROFESSIONAL,
    "manualslib.com": SourceType.REPAIR_PROFESSIONAL,
    "elektrotanya.com": SourceType.REPAIR_PROFESSIONAL,
    "partselect.com": SourceType.PARTS_CATALOG,
    "encompass.com": SourceType.PARTS_CATALOG,
    "encompassparts.com": SourceType.PARTS_CATALOG,
    "espares.co.uk": SourceType.PARTS_CATALOG,
    "sparepartsonline.com": SourceType.PARTS_CATALOG,
    # Reliability and consumer testing
    "consumerreports.org": SourceType.RELIABILITY_REPORT,
    "which.co.uk": SourceType.RELIABILITY_REPORT,
    "rtings.com": SourceType.RELIABILITY_REPORT,
    "dtest.cz": SourceType.RELIABILITY_REPORT,
    "stiftung-warentest.de": SourceType.RELIABILITY_REPORT,
    # Communities
    "reddit.com": SourceType.COMMUNITY,
    "avforums.com": SourceType.COMMUNITY,
    "badcaps.net": SourceType.COMMUNITY,
    "tomshardware.com": SourceType.COMMUNITY,
    "quora.com": SourceType.COMMUNITY,
    "stackexchange.com": SourceType.COMMUNITY,
    # Retailers
    "alza.cz": SourceType.RETAILER,
    "alza.sk": SourceType.RETAILER,
    "amazon.com": SourceType.RETAILER,
    "bestbuy.com": SourceType.RETAILER,
    "currys.co.uk": SourceType.RETAILER,
    "mediamarkt.de": SourceType.RETAILER,
}

# Path fragments that reveal the role when the domain does not.
PATH_HINTS: tuple[tuple[str, SourceType], ...] = (
    ("/service-center", SourceType.AUTHORIZED_SERVICE),
    ("/authorized-service", SourceType.AUTHORIZED_SERVICE),
    ("/servisni-stredisko", SourceType.AUTHORIZED_SERVICE),
    ("/support/repair", SourceType.AUTHORIZED_SERVICE),
    ("/repair-cost", SourceType.REPAIR_PROFESSIONAL),
    ("/service-manual", SourceType.REPAIR_PROFESSIONAL),
    ("/spare-parts", SourceType.PARTS_CATALOG),
    ("/ersatzteile", SourceType.PARTS_CATALOG),
    ("/forum", SourceType.COMMUNITY),
    ("/threads/", SourceType.COMMUNITY),
)

# Domains we refuse outright: aggregators, scraped mirrors and coupon spam.
BLOCKED_DOMAIN_MARKERS: tuple[str, ...] = (
    "coupon",
    "promo-code",
    "cheapest-deal",
    "content-farm",
    "answers-ai",
    "aicontent",
)


@dataclass(slots=True)
class SourceAssessment:
    source_type: SourceType
    quality_score: float
    accepted: bool
    reason: str


def classify_domain(domain: str, url: str = "") -> SourceType:
    domain = domain.lower()
    for known, source_type in KNOWN_DOMAINS.items():
        if domain == known or domain.endswith("." + known):
            return source_type
    lowered_url = url.lower()
    for fragment, source_type in PATH_HINTS:
        if fragment in lowered_url:
            return source_type
    return SourceType.UNKNOWN


def recency_multiplier(published_at: datetime | None, *, now: datetime | None = None) -> float:
    """Older evidence is not worthless, but it is worth less."""
    if published_at is None:
        return 0.85
    reference = now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age_years = max(0.0, (reference - published_at).days / 365.25)
    if age_years <= 2:
        return 1.0
    if age_years <= 5:
        return 0.9
    if age_years <= 8:
        return 0.75
    return 0.6


def assess_source(
    *,
    domain: str,
    url: str,
    title: str = "",
    snippet: str = "",
    published_at: datetime | None = None,
    now: datetime | None = None,
) -> SourceAssessment:
    if not domain:
        return SourceAssessment(SourceType.UNKNOWN, 0.0, False, "The URL has no host.")

    if any(marker in domain for marker in BLOCKED_DOMAIN_MARKERS):
        return SourceAssessment(
            SourceType.UNKNOWN, 0.0, False, "Domain matches a known low-quality pattern."
        )

    source_type = classify_domain(domain, url)
    score = TYPE_WEIGHT[source_type] * recency_multiplier(published_at, now=now)

    # Substance signals: a page that names prices or parts is more useful than a stub.
    text = f"{title} {snippet}".lower()
    if any(token in text for token in ("€", "eur", "usd", "$", "czk", "price", "cost")):
        score += 0.05
    if any(token in text for token in ("repair", "replace", "fault", "failure", "service")):
        score += 0.05
    if len(snippet) < 60:
        score -= 0.10

    score = round(max(0.0, min(1.0, score)), 3)
    accepted = score >= 0.30
    reason = (
        f"Classified as {source_type.value.replace('_', ' ')}."
        if accepted
        else "Score below the minimum evidence threshold."
    )
    return SourceAssessment(source_type, score, accepted, reason)


def quality_label(score: float) -> str:
    if score >= 0.85:
        return "Excellent"
    if score >= 0.65:
        return "Good"
    if score >= 0.45:
        return "Fair"
    return "Weak"
