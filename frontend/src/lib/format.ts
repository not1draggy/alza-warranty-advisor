import type {
  ConfidenceBand,
  RiskBand,
  SourceType,
  ValueOrigin,
  Verdict,
} from "@/lib/types";

export function money(value: number, currency: string): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function relativeDate(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export const VERDICT_COPY: Record<
  Verdict,
  { label: string; tone: "positive" | "caution" | "negative" | "neutral" }
> = {
  recommended: { label: "Worth buying", tone: "positive" },
  neutral: { label: "A close call", tone: "caution" },
  not_recommended: { label: "Probably skip it", tone: "negative" },
  insufficient_evidence: { label: "Not enough data", tone: "neutral" },
};

export const RISK_COPY: Record<RiskBand, string> = {
  low: "Low risk",
  moderate: "Moderate risk",
  high: "High risk",
  severe: "Severe risk",
};

export const CONFIDENCE_COPY: Record<ConfidenceBand, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export const ORIGIN_COPY: Record<ValueOrigin, string> = {
  sourced: "From a cited source",
  derived: "Calculated from cited figures",
  estimated: "Estimated — no direct source",
};

export const SOURCE_TYPE_COPY: Record<SourceType, string> = {
  manufacturer: "Manufacturer",
  authorized_service: "Authorised service",
  repair_professional: "Repair professional",
  parts_catalog: "Parts catalogue",
  reliability_report: "Reliability report",
  community: "Community",
  retailer: "Retailer",
  unknown: "Other",
};

export function qualityLabel(score: number): string {
  if (score >= 0.85) return "Excellent";
  if (score >= 0.65) return "Good";
  if (score >= 0.45) return "Fair";
  return "Weak";
}
