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
  AVAILABILITY_COPY,
  CONFIDENCE_COPY,
  counted,
  DAYS,
  DIFFICULTY_COPY,
  EVIDENCE_LEVEL_COPY,
  money,
  ORIGIN_COPY,
  ORIGIN_SHORT,
  percent,
  qualityLabel,
  relativeDate,
  RISK_COPY,
  SOURCE_TYPE_COPY,
  SOURCES,
  WEBSITES,
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
              <CardTitle>Ako riziko narastá</CardTitle>
              <CardDescription>
                Šanca, že po skončení výrobcovej záruky bude potrebná aspoň jedna
                oprava.
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
              <CardTitle>Z čoho vznikajú náklady</CardTitle>
              <CardDescription>
                Očakávané výdavky rozdelené podľa typu poruchy.
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
              Predpoklady za týmito číslami
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
                .join(" · ") || "Podrobnosti o produkte nie sú dostupné"}
            </CardDescription>
          </div>
          <Badge variant={product.identification_confidence >= 0.7 ? "data" : "outline"}>
            istota určenia {percent(product.identification_confidence)}
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
              Ďalšie možné zhody: {product.alternatives.join(", ")}
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
          Čo sa zvyčajne pokazí
        </CardTitle>
        <CardDescription>
          Zoradené podľa toho, koľko každá porucha pridáva k očakávaným výdavkom.
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
            <span className="text-muted-foreground">Šanca za obdobie</span>
            <span className="font-medium tabular-nums">
              {percent(mode.window_probability)}
            </span>
          </div>
          <Meter
            value={mode.window_probability}
            label={`Pravdepodobnosť: ${mode.name}`}
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <OriginBadge origin={mode.cost.origin} label="cena" />
          <OriginBadge origin={mode.probability_origin} label="pravdepodobnosť" />
          {mode.repair_difficulty && (
            <Badge variant="outline">
              {DIFFICULTY_COPY[mode.repair_difficulty] ?? mode.repair_difficulty}
            </Badge>
          )}
          {mode.typical_repair_days != null && (
            <Badge variant="outline">
              ~{counted(mode.typical_repair_days, ...DAYS)}
            </Badge>
          )}
          {mode.parts_availability && (
            <Badge variant="outline">
              {AVAILABILITY_COPY[mode.parts_availability] ?? mode.parts_availability}
            </Badge>
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
      {label}: {ORIGIN_SHORT[origin]}
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
        <CardTitle>Riziko vlastníctva</CardTitle>
        <CardDescription>
          Ako pravdepodobné a ako drahé sú problémy, na škále 0–100.
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
        <Meter value={risk.score / 100} label="Riziko vlastníctva" tone={tone} />

        <dl className="grid gap-3 pt-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Priemerná oprava, keď nastane</dt>
            <dd className="font-medium tabular-nums">
              {money(economics.average_repair_cost, economics.currency)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Najdrahšia jednotlivá oprava</dt>
            <dd className="font-medium tabular-nums">
              {money(economics.worst_case_repair_cost, economics.currency)}
            </dd>
          </div>
          {economics.break_even_probability != null && (
            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">Bod zvratu</dt>
              <dd className="font-medium">
                Predĺženie sa oplatí nad {percent(economics.break_even_probability)}{" "}
                šance na opravu.
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
          Aký spoľahlivý je tento odhad?
        </CardTitle>
        <CardDescription>
          Podľa toho, koľko nezávislých a kvalitných zdrojov sa zhodlo.
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
        <Meter value={confidence.score} label="Spoľahlivosť" tone={tone} />

        <p className="text-sm text-muted-foreground">
          {counted(confidence.source_count, ...SOURCES)} na{" "}
          {counted(confidence.independent_domains, ...WEBSITES)} ·{" "}
          {EVIDENCE_LEVEL_COPY[confidence.evidence_level] ?? confidence.evidence_level}{" "}
          podklady
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
          <CardTitle>Zdroje</CardTitle>
          <CardDescription>
            Pre tento produkt neprešiel kontrolou kvality žiadny verejný zdroj.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Zdroje</CardTitle>
        <CardDescription>
          Každé číslo vyššie sa dá dohľadať na jednej z týchto stránok.
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
                  {source.domain} · načítané {relativeDate(source.retrieved_at)}
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
