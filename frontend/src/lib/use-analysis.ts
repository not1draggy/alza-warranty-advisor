"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError, streamAnalysis } from "@/lib/api";
import { getSessionId } from "@/lib/session";
import type { AnalysisRequest, AnalysisResult, AnalysisStage } from "@/lib/types";

export type AnalysisPhase = "idle" | "running" | "done" | "error";

export interface AnalysisState {
  phase: AnalysisPhase;
  stages: AnalysisStage[];
  result: AnalysisResult | null;
  error: string | null;
  progress: number;
}

const INITIAL: AnalysisState = {
  phase: "idle",
  stages: [],
  result: null,
  error: null,
  progress: 0,
};

/** Drives one streaming analysis, collapsing repeated stage events into a list. */
export function useAnalysis(onComplete?: () => void) {
  const [state, setState] = useState<AnalysisState>(INITIAL);
  const controller = useRef<AbortController | null>(null);
  const completeRef = useRef(onComplete);

  useEffect(() => {
    completeRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => () => controller.current?.abort(), []);

  const reset = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    setState(INITIAL);
  }, []);

  const run = useCallback(
    async (input: Omit<AnalysisRequest, "session_id">) => {
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;

      setState({ ...INITIAL, phase: "running" });

      await streamAnalysis(
        { ...input, session_id: getSessionId() },
        {
          signal: abort.signal,
          onStage: (stage) =>
            setState((previous) => ({
              ...previous,
              progress: Math.max(previous.progress, stage.progress),
              stages: mergeStage(previous.stages, stage),
            })),
          onResult: (result) => {
            setState((previous) => ({
              ...previous,
              phase: "done",
              progress: 1,
              result,
            }));
            completeRef.current?.();
          },
          onError: (error: ApiRequestError) =>
            setState((previous) => ({
              ...previous,
              phase: "error",
              error: error.message,
            })),
        },
      );
    },
    [],
  );

  return { ...state, run, reset };
}

function mergeStage(stages: AnalysisStage[], incoming: AnalysisStage): AnalysisStage[] {
  const index = stages.findIndex((stage) => stage.stage === incoming.stage);
  if (index === -1) return [...stages, incoming];
  const next = [...stages];
  next[index] = incoming;
  return next;
}
