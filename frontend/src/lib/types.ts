export type Verdict =
  | "recommended"
  | "neutral"
  | "not_recommended"
  | "insufficient_evidence";

export type RiskBand = "low" | "moderate" | "high" | "severe";
export type ConfidenceBand = "high" | "medium" | "low";
export type EvidenceLevel = "verified" | "partial" | "modelled" | "none";
export type ValueOrigin = "sourced" | "derived" | "estimated";

export type SourceType =
  | "manufacturer"
  | "authorized_service"
  | "repair_professional"
  | "parts_catalog"
  | "reliability_report"
  | "community"
  | "retailer"
  | "unknown";

export interface Citation {
  source_id: string;
  url: string;
  domain: string;
  title: string | null;
  source_type: SourceType;
  quality_score: number;
  retrieved_at: string;
  quote: string | null;
}

export interface MoneyRange {
  currency: string;
  minimum: number;
  typical: number;
  maximum: number;
  origin: ValueOrigin;
}

export interface FailureMode {
  slug: string;
  name: string;
  component: string | null;
  description: string | null;
  annual_probability: number;
  window_probability: number;
  probability_origin: ValueOrigin;
  cost: MoneyRange;
  repair_difficulty: string | null;
  typical_repair_days: number | null;
  parts_availability: string | null;
  confidence: number;
  citations: Citation[];
}

export interface Economics {
  currency: string;
  expected_repair_cost: number;
  average_repair_cost: number;
  worst_case_repair_cost: number;
  failure_probability: number;
  warranty_price: number;
  net_value: number;
  value_ratio: number;
  break_even_probability: number | null;
}

export interface RiskAssessment {
  score: number;
  band: RiskBand;
  drivers: string[];
}

export interface ConfidenceAssessment {
  score: number;
  band: ConfidenceBand;
  evidence_level: EvidenceLevel;
  source_count: number;
  independent_domains: number;
  drivers: string[];
  uncertainties: string[];
}

export interface ProductView {
  display_name: string;
  manufacturer: string | null;
  category: string | null;
  model_number: string | null;
  release_year: number | null;
  specifications: Record<string, string>;
  aliases: string[];
  identification_confidence: number;
  alternatives: string[];
}

export interface TimelinePoint {
  year: number;
  cumulative_failure_probability: number;
  cumulative_expected_cost: number;
}

export interface VerdictView {
  decision: Verdict;
  headline: string;
  summary: string;
  reasons: string[];
}

export interface AnalysisResult {
  id: string;
  generated_at: string;
  from_cache: boolean;
  query: string;
  warranty_years: number;
  product: ProductView;
  verdict: VerdictView;
  economics: Economics;
  risk: RiskAssessment;
  confidence: ConfidenceAssessment;
  failure_modes: FailureMode[];
  timeline: TimelinePoint[];
  sources: Citation[];
  assumptions: string[];
  warnings: string[];
}

export interface AnalysisStage {
  stage: string;
  label: string;
  status: "running" | "done" | "failed";
  detail: string | null;
  progress: number;
}

export interface AnalysisRequest {
  query: string;
  warranty_years: number;
  warranty_price: number;
  currency: string;
  product_price?: number | null;
  refresh?: boolean;
  session_id?: string | null;
}

export interface HistoryEntry {
  id: string;
  created_at: string;
  query: string;
  warranty_years: number;
  warranty_price: number;
  currency: string;
  analysis_id: string | null;
  verdict: Verdict | null;
  risk_score: number | null;
  confidence: number | null;
  product_name: string | null;
}

export interface HistoryPage {
  items: HistoryEntry[];
  total: number;
}

export interface Capabilities {
  environment: string;
  llm: { configured: boolean; providers: string[] };
  search: { configured: boolean; providers: string[] };
  embeddings: { configured: boolean };
  analysis_available: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
  details?: Record<string, unknown>;
}
