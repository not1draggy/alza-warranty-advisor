"""Internal domain objects exchanged between agents.

These are the structures the language model is required to produce. Keeping them
separate from the API schemas lets the public contract evolve independently.
"""

from pydantic import BaseModel, Field

from app.schemas.common import ValueOrigin


class ProductIdentity(BaseModel):
    display_name: str
    manufacturer: str | None = None
    category: str | None = None
    model_number: str | None = None
    release_year: int | None = None
    specifications: dict[str, str] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    alternatives: list[str] = Field(default_factory=list)
    reasoning: str = ""

    @property
    def search_name(self) -> str:
        parts = [self.manufacturer or "", self.model_number or "", self.display_name]
        seen: list[str] = []
        for part in parts:
            token = part.strip()
            if token and token.lower() not in {s.lower() for s in seen}:
                seen.append(token)
        return " ".join(seen).strip() or self.display_name


class CostEvidence(BaseModel):
    currency: str = "EUR"
    minimum: float = Field(ge=0)
    typical: float = Field(ge=0)
    maximum: float = Field(ge=0)
    origin: ValueOrigin = ValueOrigin.ESTIMATED
    parts_cost: float | None = None
    labor_cost: float | None = None
    note: str | None = None


class ExtractedFailureMode(BaseModel):
    """One failure mode with its economics, as extracted from the evidence."""

    slug: str
    name: str
    component: str | None = None
    description: str | None = None
    annual_probability: float = Field(ge=0, le=1)
    probability_origin: ValueOrigin = ValueOrigin.ESTIMATED
    cost: CostEvidence
    repair_difficulty: str | None = None
    typical_repair_days: float | None = None
    parts_availability: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    # Indices into the evidence list handed to the extraction agent.
    source_indices: list[int] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    failure_modes: list[ExtractedFailureMode] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_sufficient: bool = False


class ComposedNarrative(BaseModel):
    # Derived from the verdict rather than written by the model, so the wording
    # can never contradict the recommendation.
    headline: str = ""
    summary: str
    reasons: list[str] = Field(default_factory=list)
