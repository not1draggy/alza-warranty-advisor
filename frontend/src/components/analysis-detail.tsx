"use client";

import { ExternalLink, Info, ShieldQuestion, Wrench } from "lucide-react";

import { CostBreakdown } from "@/components/charts/cost-breakdown";
import { RiskTimeline } from "@/components/charts/risk-timeline";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Meter, Separator } from "@/components/ui/misc";
import {
  CONFIDENCE_COPY,
  money,
  ORIGIN_COPY,
  percent,
  qualityLabel,
  relativeDate,
  RISK_COPY,
  SOURCE_TYPE_COPY,
} from "@/lib/format";
import type { AnalysisResult, FailureMode, ValueOrigin } from "@/lib/types";

export function AnalysisDetail({ result }: { result: AnalysisResult }) {
  const hasModes = result.failure_modes.length > 0;

  return (
    <div className="space-y-6">
      <ProductCard result={result} />

      {hasModes && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>How the risk builds up</CardTitle>
              <CardDescription>
                Chance of needing at least one repair after the manufacturer&apos;s
                warranty ends.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RiskTimeline
                points={result.timeline}
                currency={result.economics.currency}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Where the cost comes from</CardTitle>
              <CardDescription>
                Expected spending attributed to each failure type.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CostBreakdown
                modes={result.failure_modes}
                currency={result.economics.currency}
              />
            </CardContent>
          </Card>
        </div>
      )}

      {hasModes && <FailureModesCard result={result} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <RiskCard result={result} />
        <ConfidenceCard result={result} />
      </div>

      <SourcesCard result={result} />

      {result.assumptions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="size-4 text-muted-foreground" aria-hidden />
              Assumptions behind these numbers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {result.assumptions.map((assumption) => (
                <li key={assumption} className="text-sm text-muted-foreground">
                  {assumption}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ProductCard({ result }: { result: AnalysisResult }) {
  const { product } = result;
  const specs = Object.entries(product.specifications).slice(0, 6);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg">{product.display_name}</CardTitle>
            <CardDescription>
              {[product.manufacturer, product.category, product.release_year]
                .filter(Boolean)
                .join(" · ") || "Product details unavailable"}
            </CardDescription>
          </div>
          <Badge variant={product.identification_confidence >= 0.7 ? "data" : "outline"}>
            {percent(product.identification_confidence)} identification certainty
          </Badge>
        </div>
      </CardHeader>
      {(specs.length > 0 || product.alternatives.length > 0) && (
        <CardContent className="space-y-4">
          {specs.length > 0 && (
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              {specs.map(([key, value]) => (
                <div key={key} className="flex justify-between gap-4 border-b border-border/60 pb-1.5">
                  <dt className="text-muted-foreground">{humanise(key)}</dt>
                  <dd className="text-right">{value}</dd>
                </div>
              ))}
            </dl>
          )}
          {product.alternatives.length > 0 && (
            <p className="text-sm text-muted-foreground">
              Other possible matches: {product.alternatives.join(", ")}
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}

function FailureModesCard({ result }: { result: AnalysisResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="size-4 text-muted-foreground" aria-hidden />
          What usually goes wrong
        </CardTitle>
        <CardDescription>
          Ranked by how much each failure adds to expected repair spending.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {result.failure_modes.map((mode, index) => (
          <div key={mode.slug}>
            {index > 0 && <Separator className="mb-5" />}
            <FailureModeRow mode={mode} currency={result.economics.currency} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function FailureModeRow({
  mode,
  currency,
}: {
  mode: FailureMode;
  currency: string;
}) {
  return (
    <article className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-medium">{mode.name}</h3>
          {mode.description && (
            <p className="mt-1 text-pretty text-sm text-muted-foreground">
              {mode.description}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold tabular-nums">
            {money(mode.cost.typical, currency)}
          </p>
          <p className="text-xs text-muted-foreground tabular-nums">
            {money(mode.cost.minimum, currency)}–{money(mode.cost.maximum, currency)}
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <div className="mb-1.5 flex items-baseline justify-between text-xs">
            <span className="text-muted-foreground">Chance over the period</span>
            <span className="font-medium tabular-nums">
              {percent(mode.window_probability)}
            </span>
          </div>
          <Meter
            value={mode.window_probability}
            label={`${mode.name} likelihood`}
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <OriginBadge origin={mode.cost.origin} label="price" />
          <OriginBadge origin={mode.probability_origin} label="likelihood" />
          {mode.repair_difficulty && (
            <Badge variant="outline">{mode.repair_difficulty} repair</Badge>
          )}
          {mode.typical_repair_days != null && (
            <Badge variant="outline">~{mode.typical_repair_days} days</Badge>
          )}
          {mode.parts_availability && (
            <Badge variant="outline">parts: {mode.parts_availability}</Badge>
          )}
        </div>
      </div>

      {mode.citations.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {mode.citations.map((citation) => (
            <li key={`${mode.slug}-${citation.url}`}>
              <a
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                {citation.domain}
                <ExternalLink className="size-3" aria-hidden />
              </a>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function OriginBadge({ origin, label }: { origin: ValueOrigin; label: string }) {
  const variant = origin === "sourced" ? "data" : origin === "derived" ? "default" : "caution";
  return (
    <Badge variant={variant} title={ORIGIN_COPY[origin]}>
      {label}: {origin}
    </Badge>
  );
}

function RiskCard({ result }: { result: AnalysisResult }) {
  const { risk, economics } = result;
  const tone =
    risk.band === "low"
      ? "positive"
      : risk.band === "moderate"
        ? "caution"
        : "negative";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ownership risk</CardTitle>
        <CardDescription>
          How likely and how expensive trouble is, on a 0–100 scale.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end justify-between">
          <p className="text-4xl font-semibold tabular-nums">
            {risk.score.toFixed(0)}
            <span className="ml-1 text-base font-normal text-muted-foreground">
              /100
            </span>
          </p>
          <Badge
            variant={tone === "positive" ? "positive" : tone === "caution" ? "caution" : "negative"}
          >
            {RISK_COPY[risk.band]}
          </Badge>
        </div>
        <Meter value={risk.score / 100} label="Ownership risk" tone={tone} />

        <dl className="grid gap-3 pt-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Average repair, when it happens</dt>
            <dd className="font-medium tabular-nums">
              {money(economics.average_repair_cost, economics.currency)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Worst single repair</dt>
            <dd className="font-medium tabular-nums">
              {money(economics.worst_case_repair_cost, economics.currency)}
            </dd>
          </div>
          {economics.break_even_probability != null && (
            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">Break-even point</dt>
              <dd className="font-medium">
                The extension pays off above a{" "}
                {percent(economics.break_even_probability)} chance of a repair.
              </dd>
            </div>
          )}
        </dl>

        {risk.drivers.length > 0 && (
          <ul className="space-y-1.5 border-t border-border pt-4 text-sm text-muted-foreground">
            {risk.drivers.map((driver) => (
              <li key={driver}>{driver}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ConfidenceCard({ result }: { result: AnalysisResult }) {
  const { confidence } = result;
  const tone =
    confidence.band === "high"
      ? "positive"
      : confidence.band === "medium"
        ? "caution"
        : "negative";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldQuestion className="size-4 text-muted-foreground" aria-hidden />
          How reliable is this estimate?
        </CardTitle>
        <CardDescription>
          Based on how many independent, high-quality sources agreed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end justify-between">
          <p className="text-4xl font-semibold tabular-nums">
            {percent(confidence.score)}
          </p>
          <Badge
            variant={tone === "positive" ? "positive" : tone === "caution" ? "caution" : "negative"}
          >
            {CONFIDENCE_COPY[confidence.band]}
          </Badge>
        </div>
        <Meter value={confidence.score} label="Confidence" tone={tone} />

        <p className="text-sm text-muted-foreground">
          {confidence.source_count} source
          {confidence.source_count === 1 ? "" : "s"} across{" "}
          {confidence.independent_domains} website
          {confidence.independent_domains === 1 ? "" : "s"} ·{" "}
          <span className="capitalize">{confidence.evidence_level}</span> evidence
        </p>

        {confidence.drivers.length > 0 && (
          <ul className="space-y-1.5 border-t border-border pt-4 text-sm text-muted-foreground">
            {confidence.drivers.map((driver) => (
              <li key={driver}>{driver}</li>
            ))}
          </ul>
        )}
        {confidence.uncertainties.length > 0 && (
          <ul className="space-y-1.5 border-t border-border pt-4 text-sm text-caution">
            {confidence.uncertainties.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function SourcesCard({ result }: { result: AnalysisResult }) {
  if (result.sources.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sources</CardTitle>
          <CardDescription>
            No public sources passed the quality checks for this product.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sources</CardTitle>
        <CardDescription>
          Every figure above traces back to one of these pages.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {result.sources.map((source) => (
            <li
              key={source.url}
              className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
            >
              <div className="min-w-0 flex-1">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="inline-flex items-center gap-1.5 text-sm font-medium transition-colors hover:text-data"
                >
                  <span className="truncate">{source.title || source.domain}</span>
                  <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                </a>
                <p className="text-xs text-muted-foreground">
                  {source.domain} · retrieved {relativeDate(source.retrieved_at)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Badge variant="outline">
                  {SOURCE_TYPE_COPY[source.source_type]}
                </Badge>
                <Badge variant={source.quality_score >= 0.65 ? "data" : "outline"}>
                  {qualityLabel(source.quality_score)}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function humanise(key: string): string {
  return key.replace(/[_-]/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
