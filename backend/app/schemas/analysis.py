"""Request and response contracts for the warranty analysis endpoint."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    ConfidenceBand,
    DomainModel,
    EvidenceLevel,
    RiskBand,
    SourceType,
    ValueOrigin,
    Verdict,
)

SUPPORTED_CURRENCIES = {"EUR", "CZK", "USD", "GBP", "PLN", "HUF", "SKK"}


class AnalysisRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="Product name or model number")
    warranty_years: int = Field(ge=1, le=5, description="Length of the warranty extension")
    warranty_price: float = Field(ge=0, le=100_000, description="Price of the extension")
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    product_price: float | None = Field(
        default=None, ge=0, le=1_000_000, description="Optional product price for context"
    )
    refresh: bool = Field(default=False, description="Bypass the cached analysis")
    session_id: str | None = Field(default=None, max_length=64)

    @field_validator("query")
    @classmethod
    def _clean_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Query must contain visible characters.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, value: str) -> str:
        upper = value.upper()
        if upper not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency. Use one of: {sorted(SUPPORTED_CURRENCIES)}")
        return upper


class Citation(DomainModel):
    source_id: str
    url: str
    domain: str
    title: str | None = None
    source_type: SourceType = SourceType.UNKNOWN
    quality_score: float = 0.0
    retrieved_at: datetime
    quote: str | None = None


class MoneyRange(DomainModel):
    currency: str = "EUR"
    minimum: float
    typical: float
    maximum: float
    origin: ValueOrigin = ValueOrigin.ESTIMATED


class FailureModeView(DomainModel):
    slug: str
    name: str
    component: str | None = None
    description: str | None = None
    annual_probability: float = Field(ge=0, le=1)
    window_probability: float = Field(ge=0, le=1)
    probability_origin: ValueOrigin = ValueOrigin.ESTIMATED
    cost: MoneyRange
    repair_difficulty: str | None = None
    typical_repair_days: float | None = None
    parts_availability: str | None = None
    confidence: float = Field(ge=0, le=1)
    citations: list[Citation] = Field(default_factory=list)


class Economics(DomainModel):
    currency: str = "EUR"
    # Probability-weighted repair spend across the warranty window.
    expected_repair_cost: float
    # Mean cost of a repair, given that a repair happens.
    average_repair_cost: float
    worst_case_repair_cost: float
    failure_probability: float = Field(ge=0, le=1)
    warranty_price: float
    net_value: float          # expected_repair_cost - warranty_price
    value_ratio: float        # expected_repair_cost / warranty_price (0 when price is 0)
    break_even_probability: float | None = None


class RiskAssessment(DomainModel):
    score: float = Field(ge=0, le=100)
    band: RiskBand
    drivers: list[str] = Field(default_factory=list)


class ConfidenceAssessment(DomainModel):
    score: float = Field(ge=0, le=1)
    band: ConfidenceBand
    evidence_level: EvidenceLevel
    source_count: int = 0
    independent_domains: int = 0
    drivers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ProductView(DomainModel):
    display_name: str
    manufacturer: str | None = None
    category: str | None = None
    model_number: str | None = None
    release_year: int | None = None
    specifications: dict = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    identification_confidence: float = Field(default=0.0, ge=0, le=1)
    alternatives: list[str] = Field(default_factory=list)


class TimelinePoint(DomainModel):
    year: int
    cumulative_failure_probability: float = Field(ge=0, le=1)
    cumulative_expected_cost: float


class VerdictView(DomainModel):
    decision: Verdict
    headline: str
    summary: str
    reasons: list[str] = Field(default_factory=list)


class AnalysisResult(DomainModel):
    id: str
    generated_at: datetime
    from_cache: bool = False
    query: str
    warranty_years: int
    product: ProductView
    verdict: VerdictView
    economics: Economics
    risk: RiskAssessment
    confidence: ConfidenceAssessment
    failure_modes: list[FailureModeView] = Field(default_factory=list)
    timeline: list[TimelinePoint] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalysisStage(DomainModel):
    """One progress event on the streaming endpoint."""

    stage: str
    label: str
    status: str = "running"      # running | done | failed
    detail: str | None = None
    progress: float = Field(default=0.0, ge=0, le=1)


class HistoryEntry(DomainModel):
    id: str
    created_at: datetime
    query: str
    warranty_years: int
    warranty_price: float
    currency: str
    analysis_id: str | None = None
    verdict: Verdict | None = None
    risk_score: float | None = None
    confidence: float | None = None
    product_name: str | None = None


class HistoryPage(DomainModel):
    items: list[HistoryEntry]
    total: int
