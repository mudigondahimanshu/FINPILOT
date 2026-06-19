"use client";

import * as React from "react";
import {
  api,
  type Fundamentals,
  type OhlcResponse,
  type Quote,
  type TickerResult,
  type WatchlistItem,
} from "@/lib/api";
import { TickerSearch } from "@/components/market/ticker-search";
import { OhlcChart } from "@/components/market/ohlc-chart";
import { formatINR } from "@/lib/utils";
import { BookmarkPlus, BookmarkX, Loader2, TrendingDown, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";

const PERIODS = ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"];
const INTERVALS: Record<string, string> = {
  "5d": "5m", "1mo": "1h", "3mo": "1d", "6mo": "1d", "1y": "1d", "2y": "1wk", "5y": "1wk",
};

export default function MarketPage() {
  const [selected, setSelected] = React.useState<TickerResult | null>(null);
  const [period, setPeriod] = React.useState("1y");
  const [quote, setQuote] = React.useState<Quote | null>(null);
  const [ohlc, setOhlc] = React.useState<OhlcResponse | null>(null);
  const [fundamentals, setFundamentals] = React.useState<Fundamentals | null>(null);
  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>([]);
  const [loadingChart, setLoadingChart] = React.useState(false);
  const [inWatch, setInWatch] = React.useState(false);

  // Load watchlist on mount.
  React.useEffect(() => {
    api.market.watchlist().then(setWatchlist).catch(() => {});
  }, []);

  async function loadTicker(ticker: TickerResult, p: string) {
    setSelected(ticker);
    setPeriod(p);
    setLoadingChart(true);
    setOhlc(null);
    const interval = INTERVALS[p] ?? "1d";
    try {
      const [q, o, f] = await Promise.all([
        api.market.quote(ticker.symbol),
        api.market.ohlc(ticker.symbol, interval, p, true),
        api.market.fundamentals(ticker.symbol),
      ]);
      setQuote(q);
      setOhlc(o);
      setFundamentals(f);
      setInWatch(watchlist.some((w) => w.symbol === ticker.symbol));
    } catch { /* backend not up */ }
    finally { setLoadingChart(false); }
  }

  async function toggleWatch() {
    if (!selected) return;
    if (inWatch) {
      await api.market.removeWatch(selected.symbol).catch(() => {});
      setWatchlist((w) => w.filter((x) => x.symbol !== selected.symbol));
      setInWatch(false);
    } else {
      const item = await api.market.addWatch(selected.symbol, selected.exchange).catch(() => null);
      if (item) { setWatchlist((w) => [...w, item]); setInWatch(true); }
    }
  }

  const isUp = quote && quote.change >= 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6" style={{ animation: "rise 450ms ease-out both" }}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Market Data</h1>
          <p className="mt-1 text-sm text-muted-foreground">NSE / BSE live quotes via yfinance</p>
        </div>
      </div>

      {/* Search bar */}
      <div className="max-w-lg">
        <TickerSearch onSelect={(t) => loadTicker(t, period)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        {/* Main panel */}
        <div className="space-y-6">
          {selected && quote ? (
            <>
              {/* Quote card */}
              <div className="rounded-lg border border-border bg-card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-semibold font-mono">{selected.symbol.replace(/\.(NS|BO)$/, "")}</h2>
                      <span className="rounded bg-secondary px-2 py-0.5 text-xs text-muted-foreground">{selected.exchange}</span>
                    </div>
                    <p className="mt-0.5 text-sm text-muted-foreground">{fundamentals?.longName ?? selected.name}</p>
                  </div>
                  <Button variant={inWatch ? "outline" : "default"} size="sm" onClick={toggleWatch}>
                    {inWatch ? <BookmarkX className="h-4 w-4" /> : <BookmarkPlus className="h-4 w-4" />}
                    {inWatch ? "Unwatch" : "Watch"}
                  </Button>
                </div>

                <div className="mt-4 flex items-end gap-3">
                  <span className="text-4xl font-bold tabular">{formatINR(quote.price)}</span>
                  <span className={`flex items-center gap-1 text-sm font-medium ${isUp ? "text-success" : "text-destructive"}`}>
                    {isUp ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                    {isUp ? "+" : ""}{formatINR(quote.change)} ({quote.change_pct >= 0 ? "+" : ""}{quote.change_pct.toFixed(2)}%)
                  </span>
                </div>

                {fundamentals && (
                  <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-4 text-xs">
                    {[
                      { label: "52W High", value: fundamentals.fiftyTwoWeekHigh ? formatINR(fundamentals.fiftyTwoWeekHigh) : "—" },
                      { label: "52W Low", value: fundamentals.fiftyTwoWeekLow ? formatINR(fundamentals.fiftyTwoWeekLow) : "—" },
                      { label: "P/E (trailing)", value: fundamentals.trailingPE?.toFixed(1) ?? "—" },
                      { label: "P/B", value: fundamentals.priceToBook?.toFixed(2) ?? "—" },
                      { label: "Beta", value: fundamentals.beta?.toFixed(2) ?? "—" },
                      { label: "Div yield", value: fundamentals.dividendYield ? `${(fundamentals.dividendYield * 100).toFixed(2)}%` : "—" },
                    ].map(({ label, value }) => (
                      <div key={label}>
                        <p className="text-muted-foreground">{label}</p>
                        <p className="font-medium tabular">{value}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Period selector */}
              <div className="flex gap-1">
                {PERIODS.map((p) => (
                  <button
                    key={p}
                    onClick={() => loadTicker(selected, p)}
                    className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                      p === period ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>

              {/* Chart */}
              {loadingChart ? (
                <div className="flex h-72 items-center justify-center rounded-lg border border-border bg-card">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : ohlc ? (
                <OhlcChart data={ohlc} symbol={selected.symbol} />
              ) : null}

              {/* Business summary */}
              {fundamentals?.longBusinessSummary && (
                <div className="rounded-lg border border-border bg-card p-5">
                  <h3 className="mb-2 text-sm font-medium">About</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground line-clamp-4">
                    {fundamentals.longBusinessSummary}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-16 text-center">
              <p className="text-sm text-muted-foreground">Search for a ticker to see its chart and fundamentals.</p>
            </div>
          )}
        </div>

        {/* Watchlist sidebar */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-medium">Watchlist</h3>
          {watchlist.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">No symbols yet.</p>
          ) : (
            <ul className="space-y-1">
              {watchlist.map((w) => (
                <li key={w.id}>
                  <button
                    className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm hover:bg-secondary/60"
                    onClick={() => loadTicker({ symbol: w.symbol, name: w.symbol, exchange: w.exchange }, period)}
                  >
                    <span className="font-mono font-medium text-primary">{w.symbol.replace(/\.(NS|BO)$/, "")}</span>
                    <span className="text-[10px] text-muted-foreground">{w.exchange}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
