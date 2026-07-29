"""Shared schema primitives."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Verdict(StrEnum):
    RECOMMENDED = "recommended"
    NEUTRAL = "neutral"
    NOT_RECOMMENDED = "not_recommended"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceLevel(StrEnum):
    """How much of the answer rests on retrieved facts versus modelling."""

    VERIFIED = "verified"  # multiple independent, high-quality sources agree
    PARTIAL = "partial"  # some sourced facts, some modelled values
    MODELLED = "modelled"  # category baselines only, clearly labelled
    NONE = "none"  # nothing retrievable; we refuse to guess


class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class SourceType(StrEnum):
    MANUFACTURER = "manufacturer"
    AUTHORIZED_SERVICE = "authorized_service"
    REPAIR_PROFESSIONAL = "repair_professional"
    PARTS_CATALOG = "parts_catalog"
    RELIABILITY_REPORT = "reliability_report"
    COMMUNITY = "community"
    RETAILER = "retailer"
    UNKNOWN = "unknown"


class ValueOrigin(StrEnum):
    """Explicit provenance marker attached to every number we display."""

    SOURCED = "sourced"  # taken from a cited document
    DERIVED = "derived"  # computed from sourced values
    ESTIMATED = "estimated"  # model assumption, no direct source
