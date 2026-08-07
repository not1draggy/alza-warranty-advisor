"use client";

import { Check, Loader2 } from "lucide-react";

import { Meter } from "@/components/ui/misc";
import type { AnalysisStage } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ProgressStagesProps {
  stages: AnalysisStage[];
  progress: number;
}

export function ProgressStages({ stages, progress }: ProgressStagesProps) {
  return (
    <div
      className="space-y-4"
      role="status"
      aria-live="polite"
      aria-label="Priebeh analýzy"
    >
      <Meter value={progress} label="Priebeh analýzy" />
      <ol className="space-y-2.5">
        {stages.map((stage) => (
          <li
            key={stage.stage}
            className="flex animate-fade-up items-start gap-3 text-sm"
          >
            <span
              className={cn(
                "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
                stage.status === "done"
                  ? "border-data/50 bg-data/15 text-data"
                  : "border-border text-muted-foreground",
              )}
              aria-hidden
            >
              {stage.status === "done" ? (
                <Check className="size-3" />
              ) : (
                <Loader2 className="size-3 animate-spin" />
              )}
            </span>
            <span className="min-w-0">
              <span
                className={cn(
                  stage.status === "done" ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {stage.label}
              </span>
              {stage.detail && (
                <span className="ml-2 text-xs text-muted-foreground">
                  {stage.detail}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
