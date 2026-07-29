"use client";

import * as React from "react";

import { money, percent } from "@/lib/format";
import type { TimelinePoint } from "@/lib/types";
import { cn } from "@/lib/utils";

interface RiskTimelineProps {
  points: TimelinePoint[];
  currency: string;
  className?: string;
}

const WIDTH = 640;
const HEIGHT = 220;
const PADDING = { top: 18, right: 26, bottom: 34, left: 46 };

/**
 * Single-series area + line: the chance of needing at least one repair, year by
 * year. One series means no legend — the heading names it. Hovering moves a
 * crosshair and shows the exact figures for that year.
 */
export function RiskTimeline({ points, currency, className }: RiskTimelineProps) {
  const [active, setActive] = React.useState<number | null>(null);
  const gradientId = React.useId();

  if (points.length === 0) return null;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const maxProbability = Math.max(
    0.1,
    ...points.map((point) => point.cumulative_failure_probability),
  );
  const ceiling = Math.min(1, Math.ceil(maxProbability * 10) / 10);

  const x = (index: number) =>
    PADDING.left +
    (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const y = (value: number) =>
    PADDING.top + plotHeight - (value / ceiling) * plotHeight;

  const line = points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${x(index).toFixed(2)} ${y(point.cumulative_failure_probability).toFixed(2)}`,
    )
    .join(" ");
  const area = `${line} L ${x(points.length - 1).toFixed(2)} ${(PADDING.top + plotHeight).toFixed(2)} L ${x(0).toFixed(2)} ${(PADDING.top + plotHeight).toFixed(2)} Z`;

  const gridValues = [0, ceiling / 2, ceiling];
  const last = points[points.length - 1];
  const activePoint = active === null ? null : points[active];

  return (
    <figure className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full touch-none"
        role="img"
        aria-label={`Chance of needing a repair rises to ${percent(last.cumulative_failure_probability)} by year ${last.year}.`}
        onMouseLeave={() => setActive(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--data))" stopOpacity="0.28" />
            <stop offset="100%" stopColor="hsl(var(--data))" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Recessive grid and axis labels. */}
        {gridValues.map((value) => (
          <g key={value}>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={y(value)}
              y2={y(value)}
              stroke="hsl(var(--border))"
              strokeWidth={1}
            />
            <text
              x={PADDING.left - 10}
              y={y(value) + 4}
              textAnchor="end"
              className="fill-muted-foreground text-[11px]"
            >
              {percent(value)}
            </text>
          </g>
        ))}

        <path d={area} fill={`url(#${gradientId})`} />
        <path
          d={line}
          fill="none"
          stroke="hsl(var(--data))"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {points.map((point, index) => (
          <g key={point.year}>
            <text
              x={x(index)}
              y={HEIGHT - 12}
              textAnchor="middle"
              className="fill-muted-foreground text-[11px]"
            >
              Year {point.year}
            </text>
            <circle
              cx={x(index)}
              cy={y(point.cumulative_failure_probability)}
              r={active === index ? 6 : 4}
              fill="hsl(var(--data))"
              stroke="hsl(var(--card))"
              strokeWidth={2}
            />
            {/* Hit target, deliberately larger than the mark. */}
            <rect
              x={x(index) - plotWidth / (points.length * 2) - 8}
              y={PADDING.top}
              width={plotWidth / points.length + 16}
              height={plotHeight}
              fill="transparent"
              onMouseEnter={() => setActive(index)}
              onFocus={() => setActive(index)}
              tabIndex={0}
              role="button"
              aria-label={`Year ${point.year}: ${percent(point.cumulative_failure_probability)} chance, ${money(point.cumulative_expected_cost, currency)} expected`}
              className="cursor-crosshair focus:outline-none"
            />
          </g>
        ))}

        {activePoint && active !== null && (
          <line
            x1={x(active)}
            x2={x(active)}
            y1={PADDING.top}
            y2={PADDING.top + plotHeight}
            stroke="hsl(var(--data))"
            strokeWidth={1}
            strokeDasharray="3 3"
            opacity={0.7}
          />
        )}

        {/* Direct label on the final point instead of labelling every point. */}
        {active === null && (
          <text
            x={x(points.length - 1)}
            y={y(last.cumulative_failure_probability) - 12}
            textAnchor="end"
            className="fill-foreground text-[12px] font-semibold"
          >
            {percent(last.cumulative_failure_probability)}
          </text>
        )}
      </svg>

      <figcaption className="mt-1 flex min-h-[1.5rem] items-center justify-between text-xs">
        {activePoint ? (
          <span className="text-foreground">
            <span className="font-semibold">Year {activePoint.year}</span>
            <span className="text-muted-foreground">
              {" · "}
              {percent(activePoint.cumulative_failure_probability)} chance of a repair ·{" "}
              {money(activePoint.cumulative_expected_cost, currency)} expected spend
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">
            Chance of needing at least one repair, and the expected spend by then.
          </span>
        )}
      </figcaption>

      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          View as table
        </summary>
        <table className="mt-2 w-full border-collapse text-left">
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-1 pr-4 font-medium">
                Year
              </th>
              <th scope="col" className="py-1 pr-4 font-medium">
                Chance of a repair
              </th>
              <th scope="col" className="py-1 font-medium">
                Expected spend
              </th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.year} className="border-t border-border">
                <td className="py-1 pr-4">{point.year}</td>
                <td className="py-1 pr-4">
                  {percent(point.cumulative_failure_probability)}
                </td>
                <td className="py-1">
                  {money(point.cumulative_expected_cost, currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
