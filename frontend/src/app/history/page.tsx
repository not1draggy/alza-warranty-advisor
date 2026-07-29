"use client";

import { useQuery } from "@tanstack/react-query";
import { History as HistoryIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { getHistory } from "@/lib/api";
import { money, relativeDate, VERDICT_COPY } from "@/lib/format";
import { getSessionId } from "@/lib/session";

export default function HistoryPage() {
  const [sessionId, setSessionId] = React.useState("");

  React.useEffect(() => setSessionId(getSessionId()), []);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["history", sessionId],
    queryFn: () => getHistory(sessionId),
    enabled: Boolean(sessionId),
  });

  return (
    <div className="container max-w-3xl py-12">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Your searches</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Stored on this device only. Sign in from the API to keep history across
          devices.
        </p>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-20 w-full" />
          ))}
        </div>
      )}

      {isError && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            History could not be loaded. Check that the API is reachable.
          </CardContent>
        </Card>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <CardHeader className="items-center text-center">
            <span className="mb-2 flex size-11 items-center justify-center rounded-full bg-muted">
              <HistoryIcon className="size-5 text-muted-foreground" aria-hidden />
            </span>
            <CardTitle>No searches yet</CardTitle>
            <CardDescription>
              Analyse a product and it will appear here.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Link
              href="/"
              className="text-sm font-medium text-data underline underline-offset-4"
            >
              Analyse a product
            </Link>
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <ul className="space-y-3">
          {data.items.map((entry) => {
            const verdict = entry.verdict ? VERDICT_COPY[entry.verdict] : null;
            return (
              <li key={entry.id}>
                <Card>
                  <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {entry.product_name ?? entry.query}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        +{entry.warranty_years}
                        {entry.warranty_years === 1 ? " year" : " years"} ·{" "}
                        {money(entry.warranty_price, entry.currency)} ·{" "}
                        {relativeDate(entry.created_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {entry.risk_score != null && (
                        <Badge variant="outline">
                          risk {entry.risk_score.toFixed(0)}
                        </Badge>
                      )}
                      {verdict && (
                        <Badge
                          variant={
                            verdict.tone === "positive"
                              ? "positive"
                              : verdict.tone === "caution"
                                ? "caution"
                                : verdict.tone === "negative"
                                  ? "negative"
                                  : "outline"
                          }
                        >
                          {verdict.label}
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
