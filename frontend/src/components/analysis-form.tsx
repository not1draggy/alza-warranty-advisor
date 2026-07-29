"use client";

import { Loader2, Search } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const CURRENCIES = ["EUR", "CZK", "USD", "GBP", "PLN"] as const;
const YEARS = [1, 2, 3] as const;

export interface AnalysisFormValues {
  query: string;
  warranty_years: number;
  warranty_price: number;
  currency: string;
  product_price: number | null;
}

interface AnalysisFormProps {
  onSubmit: (values: AnalysisFormValues) => void;
  busy: boolean;
  disabled?: boolean;
  initialQuery?: string;
}

export function AnalysisForm({
  onSubmit,
  busy,
  disabled,
  initialQuery = "",
}: AnalysisFormProps) {
  const [query, setQuery] = React.useState(initialQuery);
  const [years, setYears] = React.useState<number>(3);
  const [price, setPrice] = React.useState("65.70");
  const [productPrice, setProductPrice] = React.useState("");
  const [currency, setCurrency] = React.useState<string>("EUR");
  const [error, setError] = React.useState<string | null>(null);

  // Picking an example fills the product field without discarding the price and
  // term the customer may already have typed.
  React.useEffect(() => {
    if (initialQuery) setQuery(initialQuery);
  }, [initialQuery]);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setError("Enter a product name or model number.");
      return;
    }
    const parsedPrice = Number.parseFloat(price.replace(",", "."));
    if (!Number.isFinite(parsedPrice) || parsedPrice < 0) {
      setError("Enter the price of the warranty extension.");
      return;
    }
    const parsedProduct = Number.parseFloat(productPrice.replace(",", "."));

    setError(null);
    onSubmit({
      query: trimmed,
      warranty_years: years,
      warranty_price: parsedPrice,
      currency,
      product_price: Number.isFinite(parsedProduct) ? parsedProduct : null,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      <div className="space-y-2">
        <Label htmlFor="product">Product name or model number</Label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            id="product"
            name="product"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Samsung 75NU8000"
            autoComplete="off"
            className="h-12 pl-10 text-base"
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "form-error" : undefined}
            disabled={disabled}
          />
        </div>
      </div>

      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-medium text-foreground/90">
          Warranty extension
        </legend>
        <div className="flex flex-wrap gap-2">
          {YEARS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setYears(value)}
              aria-pressed={years === value}
              disabled={disabled}
              className={cn(
                "h-10 rounded-md border px-4 text-sm font-medium transition-colors",
                years === value
                  ? "border-data bg-data/10 text-foreground"
                  : "border-input text-muted-foreground hover:text-foreground",
              )}
            >
              +{value} {value === 1 ? "year" : "years"}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2 sm:col-span-1">
          <Label htmlFor="price">Extension price</Label>
          <Input
            id="price"
            name="price"
            inputMode="decimal"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            placeholder="65.70"
            disabled={disabled}
          />
        </div>

        <div className="space-y-2 sm:col-span-1">
          <Label htmlFor="currency">Currency</Label>
          <select
            id="currency"
            name="currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            disabled={disabled}
            className="flex h-11 w-full rounded-md border border-input bg-background/60 px-3 text-base"
          >
            {CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2 sm:col-span-1">
          <Label htmlFor="product-price">
            Product price <span className="text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="product-price"
            name="product-price"
            inputMode="decimal"
            value={productPrice}
            onChange={(event) => setProductPrice(event.target.value)}
            placeholder="799"
            disabled={disabled}
          />
        </div>
      </div>

      {error && (
        <p id="form-error" role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={busy || disabled}>
        {busy ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Analysing…
          </>
        ) : (
          "Should I buy this warranty?"
        )}
      </Button>
    </form>
  );
}
