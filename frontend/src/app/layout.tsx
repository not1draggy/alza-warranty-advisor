import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { SiteHeader } from "@/components/site-header";
import { Providers } from "@/app/providers";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Poradca pri predĺženej záruke",
  description:
    "Zistite, či sa predĺžená záruka oplatí kúpiť — na základe toho, koľko opravy naozaj stoja.",
  robots: { index: false },
  icons: { icon: [{ url: "/favicon.svg", type: "image/svg+xml" }] },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0d1117" },
    { media: "(prefers-color-scheme: light)", color: "#f7f9fb" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="sk" suppressHydrationWarning>
      <body className={`${inter.variable} min-h-screen font-sans`}>
        <Providers>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-4 focus:py-2"
          >
            Preskočiť na obsah
          </a>
          <SiteHeader />
          <main id="main">{children}</main>
          <footer className="border-t border-border/70 py-8">
            <div className="container text-xs text-muted-foreground">
              Odhady vychádzajú z verejných informácií o opravách a sú jasne
              označené ako zo zdroja alebo odhadované. Sú orientačné, nie sú cenovou ponukou.
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
