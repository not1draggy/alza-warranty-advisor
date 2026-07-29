"use client";

import * as React from "react";

import { money, percent } from "@/lib/format";
import type { FailureMode } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CostBreakdownProps {
  modes: FailureMode[];
  currency: string;
  className?: string;
}

const ROW_HEIGHT = 34;
const BAR_HEIGHT = 10;
const LABEL_WIDTH = 168;
const VALUE_WIDTH = 76;
const WIDTH = 640;

/**
 * Horizontal bars: how much each failure contributes to the expected repair
 * spend (its chance over the period × its typical repair price). One series, so
 * no legend; every bar is directly labelled with its own value.
 */
export function CostBreakdown({ modes, currency, className }: CostBreakdownProps) {
  const [active, setActive] = React.useState<string | null>(null);

  const rows = React.useMemo(
    () =>
      modes
        .map((mode) => ({
          slug: mode.slug,
          name: mode.name,
          contribution: mode.window_probability * mode.cost.typical,
          probability: mode.window_probability,
          typical: mode.cost.typical,
          estimated: mode.cost.origin === "estimated",
        }))
        .sort((a, b) => b.contribution - a.contribution),
    [modes],
  );

  if (rows.length === 0) return null;

  const maxContribution = Math.max(...rows.map((row) => row.contribution), 1);
  const plotWidth = WIDTH - LABEL_WIDTH - VALUE_WIDTH;
  const height = rows.length * ROW_HEIGHT + 8;

  return (
    <figure className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label="Share of expected repair spending by failure type."
        onMouseLeave={() => setActive(null)}
      >
        {rows.map((row, index) => {
          const y = index * ROW_HEIGHT + 8;
          const barWidth = Math.max(
            4,
            (row.contribution / maxContribution) * plotWidth,
          );
          const isActive = active === row.slug;
          return (
            <g key={row.slug}>
              <text
                x={0}
                y={y + BAR_HEIGHT}
                className={cn(
                  "text-[12px]",
                  isActive ? "fill-foreground" : "fill-muted-foreground",
                )}
              >
                {truncate(row.name, 26)}
              </text>
              {/* Track keeps a 2px surface gap from the row above and below. */}
              <rect
                x={LABEL_WIDTH}
                y={y}
                width={plotWidth}
                height={BAR_HEIGHT}
                rx={BAR_HEIGHT / 2}
                className="fill-muted"
              />
              <rect
                x={LABEL_WIDTH}
                y={y}
                width={barWidth}
                height={BAR_HEIGHT}
                rx={4}
                fill="hsl(var(--data))"
                opacity={isActive || active === null ? 1 : 0.45}
              />
              <text
                x={WIDTH}
                y={y + BAR_HEIGHT}
                textAnchor="end"
                className="fill-foreground text-[12px] font-medium tabular-nums"
              >
                {money(row.contribution, currency)}
              </text>
              <rect
                x={0}
                y={y - 9}
                width={WIDTH}
                height={ROW_HEIGHT - 4}
                fill="transparent"
                tabIndex={0}
                role="button"
                aria-label={`${row.name}: ${money(row.contribution, currency)} of expected spending, from a ${percent(row.probability)} chance of a ${money(row.typical, currency)} repair`}
                onMouseEnter={() => setActive(row.slug)}
                onFocus={() => setActive(row.slug)}
                className="cursor-pointer focus:outline-none"
              />
            </g>
          );
        })}
      </svg>

      <figcaption className="mt-1 min-h-[1.5rem] text-xs">
        {active ? (
          <ActiveRowCaption
            row={rows.find((row) => row.slug === active)!}
            currency={currency}
          />
        ) : (
          <span className="text-muted-foreground">
            Each bar is the chance of that failure multiplied by its typical repair
            price.
          </span>
        )}
      </figcaption>
    </figure>
  );
}

function ActiveRowCaption({
  row,
  currency,
}: {
  row: {
    name: string;
    probability: number;
    typical: number;
    estimated: boolean;
  };
  currency: string;
}) {
  return (
    <span className="text-foreground">
      <span className="font-semibold">{row.name}</span>
      <span className="text-muted-foreground">
        {" · "}
        {percent(row.probability)} chance × {money(row.typical, currency)} typical
        repair
        {row.estimated ? " · price is an estimate" : ""}
      </span>
    </span>
  );
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}
