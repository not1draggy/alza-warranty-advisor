"use client";

import {
  AlertTriangle,
  CircleHelp,
  MinusCircle,
  ServerCrash,
  ThumbsUp,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { counted, money, percent, VERDICT_COPY, YEARS } from "@/lib/format";
import type { AnalysisResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICONS = {
  recommended: ThumbsUp,
  neutral: MinusCircle,
  not_recommended: XCircle,
  insufficient_evidence: CircleHelp,
  service_unavailable: ServerCrash,
} as const;

const TONE_STYLES = {
  positive: "border-positive/40 bg-positive/[0.07] text-positive",
  caution: "border-caution/40 bg-caution/[0.07] text-caution",
  negative: "border-destructive/40 bg-destructive/[0.07] text-destructive",
  neutral: "border-border bg-muted/40 text-muted-foreground",
} as const;

export function VerdictCard({ result }: { result: AnalysisResult }) {
  const { decision, headline, summary, reasons } = result.verdict;
  const copy = VERDICT_COPY[decision];
  const Icon = ICONS[decision];
  const { economics } = result;
  // No figure here was read off a page, so this has to be the first thing the
  // customer sees — above the headline, not buried beside it.
  const isEstimate = result.confidence.evidence_level === "modelled";

  return (
    <Card className="overflow-hidden">
      {isEstimate && (
        <div className="flex gap-2.5 border-b border-caution/40 bg-caution/[0.10] px-5 py-3 text-sm text-caution sm:px-6">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p className="text-pretty">
            <span className="font-semibold">Toto je odhad, nie overené údaje.</span>{" "}
            Pre tento model sme nenašli konkrétne ceny opráv, takže čísla nižšie
            vychádzajú zo všeobecných znalostí o podobných produktoch. Cenu si
            overte u predajcu.
          </p>
        </div>
      )}

      <div className={cn("border-b px-5 py-4 sm:px-6", TONE_STYLES[copy.tone])}>
        <div className="flex items-center gap-2 text-sm font-semibold">
          {/* Icon plus label: the verdict never depends on colour alone. */}
          <Icon className="size-4" aria-hidden />
          {copy.label}
        </div>
      </div>

      <CardContent className="pt-5">
        <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
          {headline}
        </h2>
        <p className="mt-3 text-pretty text-base leading-relaxed text-muted-foreground">
          {summary}
        </p>

        {decision === "service_unavailable" && (
          <div className="mt-5 rounded-md border border-destructive/40 bg-destructive/[0.06] p-4 text-sm">
            <p className="font-medium text-destructive">Ako to opraviť</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted-foreground">
              <li>
                Skontrolujte, že v <code className="text-foreground">.env</code> je
                vyplnený <code className="text-foreground">ANTHROPIC_API_KEY</code>.
              </li>
              <li>
                Po zmene <code className="text-foreground">.env</code> reštartujte API:{" "}
                <code className="text-foreground">
                  docker compose up -d --force-recreate api
                </code>
                .
              </li>
              <li>
                Presnú príčinu vypíše{" "}
                <code className="text-foreground">docker compose logs api</code> a
                zobrazí sa aj vo varovaní nižšie.
              </li>
            </ol>
          </div>
        )}

        {decision !== "insufficient_evidence" && decision !== "service_unavailable" && (
          <dl className="mt-6 grid gap-4 border-t border-border pt-5 sm:grid-cols-3">
            <Stat
              label="Šanca na opravu"
              value={percent(economics.failure_probability)}
              hint={`za ${counted(result.warranty_years, ...YEARS)}`}
            />
            <Stat
              label="Očakávané výdavky"
              value={money(economics.expected_repair_cost, economics.currency)}
              hint="vážené pravdepodobnosťou"
            />
            <Stat
              label="Cena predĺženia"
              value={money(economics.warranty_price, economics.currency)}
              hint={
                economics.net_value >= 0
                  ? `${money(economics.net_value, economics.currency)} vo váš prospech`
                  : `${money(Math.abs(economics.net_value), economics.currency)} vo váš neprospech`
              }
            />
          </dl>
        )}

        {reasons.length > 0 && (
          <ul className="mt-6 space-y-2 border-t border-border pt-5">
            {reasons.map((reason) => (
              <li key={reason} className="flex gap-2.5 text-sm text-muted-foreground">
                <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-full bg-data" />
                <span className="text-pretty">{reason}</span>
              </li>
            ))}
          </ul>
        )}

        {result.warnings.length > 0 && (
          <div className="mt-6 space-y-2 rounded-md border border-caution/40 bg-caution/[0.06] p-4">
            {result.warnings.map((warning) => (
              <p key={warning} className="flex gap-2.5 text-sm text-caution">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span className="text-pretty">{warning}</span>
              </p>
            ))}
          </div>
        )}

        {result.from_cache && (
          <Badge variant="outline" className="mt-5">
            Použité z nedávnej overenej analýzy
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums">{value}</dd>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
