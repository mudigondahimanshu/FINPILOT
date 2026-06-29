"use client";

import * as React from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Allocation, type EfficientFrontierResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertCircle, Loader2, Plus, X } from "lucide-react";

const PRESET_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "BHARTIARTL.NS"];
const COLORS = ["#6366F1", "#22C55E", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#06B6D4", "#EF4444"];

function AllocationDonut({ alloc, title }: { alloc: Allocation; title: string }) {
  const data = Object.entries(alloc.weights)
    .filter(([, w]) => w > 0.01)
    .map(([sym, w], i) => ({ name: sym.replace(/\.(NS|BO)$/, ""), value: Math.round(w * 100), color: COLORS[i % COLORS.length]! }));

  return (
    <div className="rounded-lg border border-border bg-gradient-to-br from-card to-card/50 p-5 shadow-sm">
      <h4 className="mb-1 text-sm font-semibold tracking-tight">{title}</h4>
      <div className="mb-3 flex gap-4 text-xs">
        <div>
          <p className="text-muted-foreground">Expected Return</p>
          <p className="font-semibold text-emerald-600 dark:text-emerald-400">{(alloc.expected_annual_return * 100).toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-muted-foreground">Annual Volatility</p>
          <p className="font-semibold text-amber-600 dark:text-amber-400">{(alloc.annual_volatility * 100).toFixed(1)}%</p>
        </div>
        {alloc.sharpe_ratio !== undefined && (
          <div>
            <p className="text-muted-foreground">Sharpe Ratio</p>
            <p className="font-semibold text-primary">{alloc.sharpe_ratio.toFixed(2)}</p>
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={60} paddingAngle={2}>
            {data.map((e, i) => <Cell key={i} fill={e.color} />)}
          </Pie>
          <Tooltip formatter={(v: number) => [`${v}%`, ""]} contentStyle={{ background: "hsl(0 0% 10%)", border: "1px solid hsl(0 0% 16%)", borderRadius: 8, color: "hsl(0 0% 95%)" }} />
          <Legend iconType="circle" iconSize={7} formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
        </PieChart>
      </ResponsiveContainer>
      <div className="mt-3 space-y-1 border-t border-border/50 pt-3">
        {data.map((item, i) => (
          <div key={i} className="flex justify-between text-xs">
            <span className="font-mono text-muted-foreground">{item.name}</span>
            <span className="font-medium" style={{ color: item.color }}>{item.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function OptimizePage() {
  const [symbols, setSymbols] = React.useState<string[]>(PRESET_SYMBOLS);
  const [newSym, setNewSym] = React.useState("");
  const [result, setResult] = React.useState<EfficientFrontierResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  function addSymbol() {
    const s = newSym.trim().toUpperCase();
    if (s && !symbols.includes(s) && symbols.length < 15) {
      setSymbols([...symbols, s]);
      setNewSym("");
    }
  }

  async function runOptimizer() {
    setError(null);
    setLoading(true);
    try {
      const res = await api.optimizer.efficientFrontier({ symbols, n_portfolios: 2000 });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed");
    } finally {
      setLoading(false);
    }
  }

  const frontierData = result?.frontier.map((p) => ({
    vol: parseFloat((p.volatility * 100).toFixed(2)),
    ret: parseFloat((p.expected_return * 100).toFixed(2)),
    sharpe: p.sharpe,
  })) ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-8" style={{ animation: "rise 450ms ease-out both" }}>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Portfolio Optimizer</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Markowitz Modern Portfolio Theory — efficient frontier visualization with Sharpe ratio maximization
        </p>
      </div>

      {/* Symbol selector */}
      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold tracking-tight">Portfolio Symbols ({symbols.length}/15)</h3>
        <div className="mb-4 flex flex-wrap gap-2">
          {symbols.map((s) => (
            <span key={s} className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs font-mono font-medium text-primary">
              {s.replace(/\.(NS|BO)$/, "")}
              <button onClick={() => setSymbols(symbols.filter((x) => x !== s))} className="hover:text-primary/60">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            value={newSym}
            onChange={(e) => setNewSym(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addSymbol())}
            placeholder="RELIANCE.NS"
            className="max-w-[220px] font-mono text-sm"
          />
          <Button variant="outline" size="sm" onClick={addSymbol} className="gap-1">
            <Plus className="h-4 w-4" />Add
          </Button>
          <Button onClick={runOptimizer} disabled={loading || symbols.length < 2} className="ml-auto gap-2">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Optimizing…" : "Run Optimizer"}
          </Button>
        </div>
        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}
      </div>

      {result && (
        <>
          {/* Efficient frontier scatter */}
          <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold tracking-tight">Efficient Frontier</h3>
            <p className="mb-4 text-xs text-muted-foreground">Scatter plot showing risk-return tradeoff across 2000 simulated portfolios</p>
            <div className="rounded-lg bg-secondary/20 p-4">
              <ResponsiveContainer width="100%" height={350}>
                <ScatterChart margin={{ left: 30, right: 30, bottom: 30, top: 10 }}>
                  <XAxis
                    dataKey="vol"
                    name="Volatility"
                    unit="%"
                    tick={{ fontSize: 12, fill: "hsl(0 0% 55%)" }}
                    axisLine={false}
                    tickLine={false}
                    label={{ value: "Annual Volatility (%)", position: "insideBottomRight", offset: -10, fontSize: 12, fill: "hsl(0 0% 55%)" }}
                  />
                  <YAxis
                    dataKey="ret"
                    name="Return"
                    unit="%"
                    tick={{ fontSize: 12, fill: "hsl(0 0% 55%)" }}
                    axisLine={false}
                    tickLine={false}
                    label={{ value: "Annual Return (%)", angle: -90, position: "insideLeft", offset: 10, fontSize: 12, fill: "hsl(0 0% 55%)" }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3", stroke: "hsl(0 0% 40%)" }}
                    formatter={(v: number, name: string) => [name === "ret" ? `${v.toFixed(2)}%` : `${v.toFixed(2)}%`, name === "ret" ? "Return" : "Volatility"]}
                    contentStyle={{ background: "hsl(0 0% 10%)", border: "1px solid hsl(0 0% 20%)", borderRadius: 8, color: "hsl(0 0% 95%)" }}
                  />
                  <Scatter data={frontierData} fill="#6366F1" fillOpacity={0.6} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Key allocations */}
          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-tight">Recommended Allocations</h3>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <AllocationDonut alloc={result.max_sharpe} title="⭐ Max Sharpe Ratio" />
              <AllocationDonut alloc={result.min_volatility} title="🛡️ Min Volatility" />
              <AllocationDonut alloc={result.presets.moderate} title="⚖️ Moderate (18% vol cap)" />
            </div>
          </div>

          {/* Preset risk profiles */}
          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-tight">Risk Profiles</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { key: "conservative", label: "Conservative", emoji: "🏦" },
                { key: "moderate", label: "Moderate", emoji: "⚖️" },
                { key: "aggressive", label: "Aggressive", emoji: "🚀" },
              ].map(({ key, label, emoji }) => {
                const alloc = result.presets[key as keyof typeof result.presets];
                return (
                  <div key={key} className="rounded-lg border border-border bg-gradient-to-br from-card to-card/50 p-4 shadow-sm">
                    <p className="mb-3 flex items-center gap-2 font-semibold text-sm">
                      <span>{emoji}</span> {label}
                    </p>
                    <div className="space-y-2 mb-3 pb-3 border-b border-border/50">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">Annual Return</span>
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">{(alloc.expected_annual_return * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">Volatility</span>
                        <span className="font-semibold text-amber-600 dark:text-amber-400">{(alloc.annual_volatility * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {Object.entries(alloc.weights)
                        .filter(([, w]) => w > 0.01)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 5)
                        .map(([sym, w], i) => (
                          <div key={sym} className="flex justify-between text-xs">
                            <span className="text-muted-foreground font-mono">{sym.replace(/\.(NS|BO)$/, "")}</span>
                            <span className="font-semibold" style={{ color: COLORS[i % COLORS.length] }}>{(w * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
