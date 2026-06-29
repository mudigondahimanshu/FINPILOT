"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type OhlcResponse } from "@/lib/api";
import { formatINR } from "@/lib/utils";

interface Props {
  data: OhlcResponse;
  symbol: string;
}

const INTERVALS = [
  { label: "1D", value: "1d", period: "5d" },
  { label: "1W", value: "1wk", period: "6mo" },
  { label: "1M", value: "1mo", period: "2y" },
  { label: "3M", value: "1d", period: "3mo" },
  { label: "1Y", value: "1d", period: "1y" },
  { label: "5Y", value: "1wk", period: "5y" },
];

function CustomOhlcTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: "hsl(0 0% 10%)",
        border: "1px solid hsl(0 0% 16%)",
        borderRadius: 8,
        padding: "8px 12px",
      }}>
        <div style={{ color: "#ffffff", fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
          {label}
        </div>
        {payload.map((entry: any, i: number) => (
          <div key={i} style={{ color: "#ffffff", fontSize: 12, marginBottom: i < payload.length - 1 ? 3 : 0 }}>
            <span style={{ color: entry.color }}>{entry.name}:</span> {formatINR(entry.value)}
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export function OhlcChart({ data, symbol }: Props) {
  const chartData = data.candles.map((c, i) => ({
    t: new Date(c.timestamp).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
    close: Number(c.close),
    sma20: data.sma20?.[i] ?? null,
    sma50: data.sma50?.[i] ?? null,
    ema20: data.ema20?.[i] ?? null,
  }));

  const prices = data.candles.map((c) => Number(c.close));
  const minPrice = Math.min(...prices) * 0.98;
  const maxPrice = Math.max(...prices) * 1.02;
  const isUp = prices.length > 1 && prices[prices.length - 1] >= prices[0];

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-medium">{symbol} — Price chart</h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ left: 0, right: 10, top: 4, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={isUp ? "#22C55E" : "#EF4444"} stopOpacity={0.15} />
              <stop offset="95%" stopColor={isUp ? "#22C55E" : "#EF4444"} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 16%)" vertical={false} />
          <XAxis
            dataKey="t"
            tick={{ fontSize: 10, fill: "hsl(0 0% 55%)" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minPrice, maxPrice]}
            tickFormatter={(v) => `₹${(v / 1000).toFixed(1)}k`}
            tick={{ fontSize: 10, fill: "hsl(0 0% 55%)" }}
            axisLine={false}
            tickLine={false}
            width={55}
          />
          <Tooltip content={<CustomOhlcTooltip />} />
          <Legend
            iconType="line"
            iconSize={10}
            formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>}
          />
          <Area
            type="monotone"
            dataKey="close"
            name="Close"
            stroke={isUp ? "#22C55E" : "#EF4444"}
            strokeWidth={2}
            fill="url(#priceGrad)"
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Area
            type="monotone"
            dataKey="sma20"
            name="SMA 20"
            stroke="#6366F1"
            strokeWidth={1.5}
            fill="none"
            dot={false}
            activeDot={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="sma50"
            name="SMA 50"
            stroke="#F59E0B"
            strokeWidth={1.5}
            fill="none"
            dot={false}
            activeDot={false}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
