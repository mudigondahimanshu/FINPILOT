"use client";

import * as React from "react";
import { api, type TradeCreate, type TradeRead } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2 } from "lucide-react";

interface Props {
  defaultSymbol?: string;
  onTraded: (trade: TradeRead) => void;
}

export function OrderForm({ defaultSymbol = "", onTraded }: Props) {
  const [form, setForm] = React.useState<TradeCreate>({
    symbol: defaultSymbol,
    side: "buy",
    quantity: 1,
  });
  const [useMarket, setUseMarket] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const body: TradeCreate = { ...form };
      if (useMarket) delete body.price;
      const trade = await api.portfolio.placeOrder(body);
      onTraded(trade);
      setForm((f) => ({ ...f, quantity: 1 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>Symbol</Label>
        <Input
          value={form.symbol}
          onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
          placeholder="RELIANCE.NS"
          required
        />
      </div>

      {/* Buy / Sell toggle */}
      <div className="flex rounded-lg overflow-hidden border border-border">
        {(["buy", "sell"] as const).map((side) => (
          <button
            key={side}
            type="button"
            onClick={() => setForm({ ...form, side })}
            className={`flex-1 py-2 text-sm font-medium transition-colors capitalize ${
              form.side === side
                ? side === "buy"
                  ? "bg-success text-white"
                  : "bg-destructive text-white"
                : "text-muted-foreground hover:bg-secondary/60"
            }`}
          >
            {side}
          </button>
        ))}
      </div>

      <div className="space-y-1.5">
        <Label>Quantity</Label>
        <Input
          type="number"
          min="0.001"
          step="0.001"
          value={form.quantity}
          onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
          required
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="use-market"
          type="checkbox"
          checked={useMarket}
          onChange={(e) => setUseMarket(e.target.checked)}
          className="h-4 w-4 rounded border-border"
        />
        <label htmlFor="use-market" className="text-sm text-muted-foreground cursor-pointer">
          Market order (fill at current price)
        </label>
      </div>

      {!useMarket && (
        <div className="space-y-1.5">
          <Label>Limit price (₹)</Label>
          <Input
            type="number"
            min="0.01"
            step="0.01"
            value={form.price ?? ""}
            onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
            required
          />
        </div>
      )}

      {error && (
        <p className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}
        </p>
      )}

      <Button type="submit" disabled={saving} className="w-full" variant={form.side === "buy" ? "default" : "destructive"}>
        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
        {form.side === "buy" ? "Buy" : "Sell"} {form.symbol || "…"}
      </Button>
    </form>
  );
}
