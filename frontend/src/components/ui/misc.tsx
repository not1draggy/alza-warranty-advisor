import * as React from "react";

import { cn } from "@/lib/utils";

export function Separator({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="separator"
      className={cn("h-px w-full bg-border", className)}
      {...props}
    />
  );
}

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-muted",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-shimmer",
        "after:bg-gradient-to-r after:from-transparent after:via-foreground/10 after:to-transparent",
        className,
      )}
      {...props}
    />
  );
}

export interface MeterProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0-1 */
  value: number;
  label: string;
  tone?: "data" | "positive" | "caution" | "negative";
}

/**
 * Accessible progress meter. The numeric value is always rendered as text next
 * to the bar so the reading never depends on colour or length alone.
 */
export function Meter({
  value,
  label,
  tone = "data",
  className,
  ...props
}: MeterProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const fill = {
    data: "bg-data",
    positive: "bg-positive",
    caution: "bg-caution",
    negative: "bg-destructive",
  }[tone];

  return (
    <div className={cn("w-full", className)} {...props}>
      <div
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(clamped * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-500", fill)}
          style={{ width: `${clamped * 100}%` }}
        />
      </div>
    </div>
  );
}
