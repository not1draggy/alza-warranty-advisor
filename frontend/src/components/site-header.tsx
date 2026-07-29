import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-md text-sm font-semibold tracking-tight"
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-data/15 text-data">
            <ShieldCheck className="size-[18px]" aria-hidden />
          </span>
          <span>
            Warranty Advisor
            <span className="ml-1.5 text-muted-foreground">AI</span>
          </span>
        </Link>

        <div className="flex items-center gap-1">
          <Link
            href="/history"
            className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            History
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
