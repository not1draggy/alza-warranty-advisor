"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RotateCcw } from "lucide-react";
import * as React from "react";

import { AnalysisDetail } from "@/components/analysis-detail";
import { AnalysisForm, type AnalysisFormValues } from "@/components/analysis-form";
import { ProgressStages } from "@/components/progress-stages";
import { VerdictCard } from "@/components/verdict-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getCapabilities } from "@/lib/api";
import { useAnalysis } from "@/lib/use-analysis";

const EXAMPLES = [
  "Samsung 75NU8000",
  "LG OLED55C1",
  "Bosch WAN28281GB",
  "Dyson V15 Detect",
];

export default function HomePage() {
  const queryClient = useQueryClient();
  const [example, setExample] = React.useState("");

  const { data: capabilities } = useQuery({
    queryKey: ["capabilities"],
    queryFn: getCapabilities,
    staleTime: 5 * 60_000,
  });

  const analysis = useAnalysis(() => {
    void queryClient.invalidateQueries({ queryKey: ["history"] });
  });

  const resultRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (analysis.phase === "done" && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [analysis.phase]);

  function handleSubmit(values: AnalysisFormValues) {
    void analysis.run(values);
  }

  const providersMissing = capabilities && !capabilities.analysis_available;

  return (
    <div className="surface-grid">
      <section className="container max-w-3xl py-12 sm:py-16">
        <div className="mb-8 text-center">
          <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Should you buy the extended warranty?
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-pretty text-muted-foreground">
            Tell us the product and the price of the extension. We look up what
            repairs actually cost after the manufacturer&apos;s warranty ends, and
            show you the maths.
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
            <AnalysisForm
              onSubmit={handleSubmit}
              busy={analysis.phase === "running"}
              disabled={providersMissing}
              initialQuery={example}
            />
          </CardContent>
        </Card>

        {providersMissing && (
          <div className="mt-4 flex gap-2.5 rounded-md border border-caution/40 bg-caution/[0.06] p-4 text-sm text-caution">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="text-pretty">
              This deployment has no{" "}
              {!capabilities?.llm.configured ? "language model" : "search provider"}{" "}
              configured, so analyses cannot run. Set the provider keys in the
              environment and restart the API.
            </p>
          </div>
        )}

        {analysis.phase === "idle" && !providersMissing && (
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            <span className="text-xs text-muted-foreground">Try:</span>
            {EXAMPLES.map((item) => (
              <Button
                key={item}
                variant="outline"
                size="sm"
                onClick={() => setExample(item)}
              >
                {item}
              </Button>
            ))}
          </div>
        )}

        {analysis.phase === "running" && (
          <Card className="mt-6">
            <CardContent className="pt-6">
              <ProgressStages stages={analysis.stages} progress={analysis.progress} />
            </CardContent>
          </Card>
        )}

        {analysis.phase === "error" && (
          <Card className="mt-6 border-destructive/40">
            <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
              <p className="flex gap-2.5 text-sm text-destructive">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span className="text-pretty">{analysis.error}</span>
              </p>
              <Button variant="outline" size="sm" onClick={analysis.reset}>
                <RotateCcw aria-hidden />
                Start over
              </Button>
            </CardContent>
          </Card>
        )}
      </section>

      {analysis.result && (
        <section
          ref={resultRef}
          className="container max-w-5xl animate-fade-up pb-20"
          aria-live="polite"
        >
          <div className="space-y-6">
            <VerdictCard result={analysis.result} />
            <AnalysisDetail result={analysis.result} />
          </div>
        </section>
      )}
    </div>
  );
}
