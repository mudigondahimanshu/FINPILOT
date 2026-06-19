"use client";

import * as React from "react";
import { api, type Holding, type PortfolioSummary, type TradeRead } from "@/lib/api";
import { OrderForm } from "@/components/trading/order-form";
import { formatINR } from "@/lib/utils";
import { Loader2, TrendingDown, TrendingUp } from "lucide-react";

export default function TradingPage() {
  const [summary, setSummary] = React.useState<PortfolioSummary | null>(null);
  const [trades, setTrades] = React.useState<TradeRead[]>([]);
  const [loading, setLoading] = React.useState(true);

  async function load() {
    try {
      const [s, t] = await Promise.all([
        api.portfolio.summary(),
        api.portfolio.trades(20),
      ]);
      setSummary(s);
      setTrades(t);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  }

  React.useEffect(() => { load(); }, []);

  function onTraded(trade: TradeRead) {
    setTrades((prev) => [trade, ...prev]);
    load(); // refresh summary
  }

  const pnl = summary ? Number(summary.unrealized_pnl ?? 0) : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-8" style={{ animation: "rise 450ms ease-out both" }}>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Paper Trading</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Educational simulation only — no real money involved.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          {/* Left: portfolio summary + holdings */}
          <div className="space-y-6">
            {/* KPIs */}
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                { label: "Cash balance", value: summary ? formatINR(Number(summary.portfolio.cash_balance)) : "—", color: "text-foreground" },
                { label: "Market value", value: summary?.market_value ? formatINR(Number(summary.market_value)) : "—", color: "text-foreground" },
                { label: "Unrealized P&L", value: summary ? formatINR(Math.abs(pnl)) : "—", color: pnl >= 0 ? "text-success" : "text-destructive" },
              ].map(({ label, value, color }) => (
                <div key={label} className="rounded-lg border border-border bg-card p-5">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
                  <p className={`mt-2 text-2xl font-semibold tabular ${color}`}>{value}</p>
                </div>
              ))}
            </div>

            {/* Holdings table */}
            <div className="rounded-lg border border-border overflow-hidden">
              <div className="border-b border-border bg-card/60 px-4 py-3">
                <h3 className="text-sm font-medium">Open positions</h3>
              </div>
              {!summary || summary.holdings.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">No open positions.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-xs font-medium uppercase tracking-wide text-muted-foreground bg-card/40">
                    <tr>
                      {["Symbol", "Qty", "Avg cost", "Current", "P&L", "P&L %"].map((h) => (
                        <th key={h} className="px-4 py-2 text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {summary.holdings.map((h: Holding) => {
                      const pl = h.unrealized_pnl ? Number(h.unrealized_pnl) : null;
                      const plPct = h.unrealized_pnl_pct ? Number(h.unrealized_pnl_pct) : null;
                      const isUp = pl !== null && pl >= 0;
                      return (
                        <tr key={h.symbol} className="hover:bg-secondary/30">
                          <td className="px-4 py-3 font-mono font-semibold text-primary">{h.symbol.replace(/\.(NS|BO)$/, "")}</td>
                          <td className="px-4 py-3 tabular">{Number(h.quantity).toFixed(2)}</td>
                          <td className="px-4 py-3 tabular">{formatINR(Number(h.avg_cost))}</td>
                          <td className="px-4 py-3 tabular">{h.current_price ? formatINR(Number(h.current_price)) : "—"}</td>
                          <td className={`px-4 py-3 tabular font-medium ${pl !== null ? (isUp ? "text-success" : "text-destructive") : ""}`}>
                            {pl !== null ? `${isUp ? "+" : ""}${formatINR(Math.abs(pl))}` : "—"}
                          </td>
                          <td className={`px-4 py-3 tabular text-xs ${plPct !== null ? (isUp ? "text-success" : "text-destructive") : ""}`}>
                            {plPct !== null ? `${isUp ? "+" : ""}${plPct.toFixed(2)}%` : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* Trade history */}
            <div className="rounded-lg border border-border overflow-hidden">
              <div className="border-b border-border bg-card/60 px-4 py-3">
                <h3 className="text-sm font-medium">Recent trades</h3>
              </div>
              {trades.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No trades yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-xs font-medium uppercase tracking-wide text-muted-foreground bg-card/40">
                    <tr>
                      {["Symbol", "Side", "Qty", "Price", "Time"].map((h) => (
                        <th key={h} className="px-4 py-2 text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {trades.map((t) => (
                      <tr key={t.id} className="hover:bg-secondary/30">
                        <td className="px-4 py-3 font-mono font-semibold">{t.symbol.replace(/\.(NS|BO)$/, "")}</td>
                        <td className={`px-4 py-3 font-medium capitalize ${t.side === "buy" ? "text-success" : "text-destructive"}`}>
                          {t.side === "buy" ? <TrendingUp className="inline h-3.5 w-3.5 mr-1" /> : <TrendingDown className="inline h-3.5 w-3.5 mr-1" />}
                          {t.side}
                        </td>
                        <td className="px-4 py-3 tabular">{Number(t.quantity).toFixed(2)}</td>
                        <td className="px-4 py-3 tabular">{formatINR(Number(t.price))}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {new Date(t.executed_at).toLocaleString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Right: order form */}
          <div className="rounded-lg border border-border bg-card p-5 h-fit">
            <h3 className="mb-4 text-sm font-medium">Place order</h3>
            <OrderForm onTraded={onTraded} />
          </div>
        </div>
      )}
    </div>
  );
}
