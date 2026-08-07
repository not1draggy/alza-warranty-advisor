import type {
  ConfidenceBand,
  RiskBand,
  SourceType,
  ValueOrigin,
  Verdict,
} from "@/lib/types";

const LOCALE = "sk-SK";

export function money(value: number, currency: string): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)} %`;
}

export function relativeDate(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

/**
 * Slovak nouns take three forms after a number — 1 rok, 2 roky, 5 rokov — so a
 * count cannot simply be concatenated with a fixed word.
 */
export function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) return one;
  if (count >= 2 && count <= 4) return few;
  return many;
}

export function counted(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  return `${count} ${plural(count, one, few, many)}`;
}

export const YEARS = ["rok", "roky", "rokov"] as const;
export const SOURCES = ["zdroj", "zdroje", "zdrojov"] as const;
export const WEBSITES = ["webstránka", "webstránky", "webstránok"] as const;
export const DAYS = ["deň", "dni", "dní"] as const;

export const VERDICT_COPY: Record<
  Verdict,
  { label: string; tone: "positive" | "caution" | "negative" | "neutral" }
> = {
  recommended: { label: "Oplatí sa", tone: "positive" },
  neutral: { label: "Tesné", tone: "caution" },
  not_recommended: { label: "Skôr nie", tone: "negative" },
  insufficient_evidence: { label: "Málo podkladov", tone: "neutral" },
  service_unavailable: { label: "Služba nedostupná", tone: "negative" },
};

export const RISK_COPY: Record<RiskBand, string> = {
  low: "Nízke riziko",
  moderate: "Stredné riziko",
  high: "Vysoké riziko",
  severe: "Veľmi vysoké riziko",
};

export const CONFIDENCE_COPY: Record<ConfidenceBand, string> = {
  high: "Vysoká spoľahlivosť",
  medium: "Stredná spoľahlivosť",
  low: "Nízka spoľahlivosť",
};

export const ORIGIN_COPY: Record<ValueOrigin, string> = {
  sourced: "Z citovaného zdroja",
  derived: "Vypočítané z citovaných čísel",
  estimated: "Odhad — bez priameho zdroja",
};

/** Short form for the badge beside a value; the full wording is the tooltip. */
export const ORIGIN_SHORT: Record<ValueOrigin, string> = {
  sourced: "zo zdroja",
  derived: "vypočítané",
  estimated: "odhad",
};

export const SOURCE_TYPE_COPY: Record<SourceType, string> = {
  manufacturer: "Výrobca",
  authorized_service: "Autorizovaný servis",
  repair_professional: "Profesionálny servis",
  parts_catalog: "Katalóg dielov",
  reliability_report: "Správa o poruchovosti",
  community: "Komunita",
  retailer: "Predajca",
  unknown: "Iné",
};

export const EVIDENCE_LEVEL_COPY: Record<string, string> = {
  verified: "overené",
  partial: "čiastočné",
  modelled: "modelované",
  none: "žiadne",
};

export const DIFFICULTY_COPY: Record<string, string> = {
  easy: "ľahká oprava",
  moderate: "stredne náročná oprava",
  hard: "náročná oprava",
};

export const AVAILABILITY_COPY: Record<string, string> = {
  good: "diely dostupné",
  limited: "diely obmedzene dostupné",
  scarce: "diely ťažko dostupné",
};

export function qualityLabel(score: number): string {
  if (score >= 0.85) return "Výborný";
  if (score >= 0.65) return "Dobrý";
  if (score >= 0.45) return "Priemerný";
  return "Slabý";
}
