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
    <div className="rounded-lg border border-border bg-card p-5">
      <h4 className="mb-1 text-sm font-medium">{title}</h4>
      <div className="mb-2 flex gap-4 text-xs text-muted-foreground">
        <span>Return: <strong className="text-foreground">{(alloc.expected_annual_return * 100).toFixed(1)}%</strong></span>
        <span>Vol: <strong className="text-foreground">{(alloc.annual_volatility * 100).toFixed(1)}%</strong></span>
        {alloc.sharpe_ratio !== undefined && (
          <span>Sharpe: <strong className="text-foreground">{alloc.sharpe_ratio.toFixed(2)}</strong></span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={60} paddingAngle={2}>
            {data.map((e, i) => <Cell key={i} fill={e.color} />)}
          </Pie>
          <Tooltip formatter={(v: number) => [`${v}%`, ""]} contentStyle={{ background: "hsl(0 0% 10%)", border: "1px solid hsl(0 0% 16%)", borderRadius: 8 }} />
          <Legend iconType="circle" iconSize={7} formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
        </PieChart>
      </ResponsiveContainer>
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
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio Optimizer</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Markowitz Modern Portfolio Theory — efficient frontier + Sharpe ratio maximization.
        </p>
      </div>

      {/* Symbol selector */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-medium">Symbols ({symbols.length}/15)</h3>
        <div className="mb-3 flex flex-wrap gap-2">
          {symbols.map((s) => (
            <span key={s} className="flex items-center gap-1 rounded-full bg-secondary px-3 py-1 text-xs font-mono font-medium">
              {s.replace(/\.(NS|BO)$/, "")}
              <button onClick={() => setSymbols(symbols.filter((x) => x !== s))}>
                <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={newSym}
            onChange={(e) => setNewSym(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addSymbol())}
            placeholder="RELIANCE.NS"
            className="max-w-[220px] font-mono text-sm"
          />
          <Button variant="outline" size="sm" onClick={addSymbol}><Plus className="h-4 w-4" />Add</Button>
          <Button onClick={runOptimizer} disabled={loading || symbols.length < 2} className="ml-auto">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Optimizing…" : "Run optimizer"}
          </Button>
        </div>
        {error && (
          <p className="mt-3 flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />{error}
          </p>
        )}
      </div>

      {result && (
        <>
          {/* Efficient frontier scatter */}
          <div className="rounded-lg border border-border bg-card p-5">
            <h3 className="mb-4 text-sm font-medium">Efficient Frontier</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ left: 10, right: 20, bottom: 10 }}>
                <XAxis
                  dataKey="vol"
                  name="Volatility"
                  unit="%"
                  tick={{ fontSize: 11, fill: "hsl(0 0% 55%)" }}
                  axisLine={false}
                  tickLine={false}
                  label={{ value: "Annual Volatility (%)", position: "insideBottom", offset: -5, fontSize: 11, fill: "hsl(0 0% 55%)" }}
                />
                <YAxis
                  dataKey="ret"
                  name="Return"
                  unit="%"
                  tick={{ fontSize: 11, fill: "hsl(0 0% 55%)" }}
                  axisLine={false}
                  tickLine={false}
                  label={{ value: "Annual Return (%)", angle: -90, position: "insideLeft", offset: 10, fontSize: 11, fill: "hsl(0 0% 55%)" }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  formatter={(v: number, name: string) => [`${v.toFixed(2)}%`, name]}
                  contentStyle={{ background: "hsl(0 0% 10%)", border: "1px solid hsl(0 0% 16%)", borderRadius: 8 }}
                />
                <Scatter data={frontierData} fill="#6366F1" opacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Allocation cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <AllocationDonut alloc={result.max_sharpe} title="Max Sharpe ratio" />
            <AllocationDonut alloc={result.min_volatility} title="Min volatility" />
            <AllocationDonut alloc={result.presets.moderate} title="Moderate (18% vol cap)" />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { key: "conservative", label: "Conservative" },
              { key: "moderate", label: "Moderate" },
              { key: "aggressive", label: "Aggressive" },
            ].map(({ key, label }) => {
              const alloc = result.presets[key as keyof typeof result.presets];
              return (
                <div key={key} className="rounded-lg border border-border bg-card p-4 text-sm">
                  <p className="font-medium mb-2">{label}</p>
                  <p className="text-muted-foreground">Return: <span className="text-foreground font-mono">{(alloc.expected_annual_return * 100).toFixed(1)}%</span></p>
                  <p className="text-muted-foreground">Vol: <span className="text-foreground font-mono">{(alloc.annual_volatility * 100).toFixed(1)}%</span></p>
                  <div className="mt-2 space-y-0.5">
                    {Object.entries(alloc.weights)
                      .filter(([, w]) => w > 0.01)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 4)
                      .map(([sym, w]) => (
                        <div key={sym} className="flex justify-between text-xs">
                          <span className="text-muted-foreground font-mono">{sym.replace(/\.(NS|BO)$/, "")}</span>
                          <span>{(w * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
