"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type SpendForecast } from "@/lib/api";
import { formatINR } from "@/lib/utils";

interface Props {
  data: SpendForecast;
  historicalSeries?: number[];
}

type Mode = "ensemble" | "arima" | "lstm";

export function ForecastChart({ data, historicalSeries = [] }: Props) {
  const [mode, setMode] = React.useState<Mode>("ensemble");

  const combined = React.useMemo(() => {
    const hist = historicalSeries.map((v, i) => ({
      day: -(historicalSeries.length - i),
      actual: v,
      forecast: undefined as number | undefined,
      ci_lo: undefined as number | undefined,
      ci_hi: undefined as number | undefined,
    }));
    const fcast = data.ensemble.map((_, i) => ({
      day: i + 1,
      actual: undefined as number | undefined,
      forecast:
        mode === "ensemble"
          ? data.ensemble[i]
          : mode === "arima"
            ? data.arima[i]
            : data.lstm[i],
      ci_lo: mode === "arima" ? data.arima_ci_lower[i] : undefined,
      ci_hi: mode === "arima" ? data.arima_ci_upper[i] : undefined,
    }));
    return [...hist.slice(-30), ...fcast];
  }, [data, historicalSeries, mode]);

  const modes: { value: Mode; label: string }[] = [
    { value: "ensemble", label: "Ensemble" },
    { value: "arima", label: "ARIMA" },
    { value: "lstm", label: "LSTM" },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1.5">
        {modes.map((m) => (
          <button
            key={m.value}
            onClick={() => setMode(m.value)}
            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              mode === m.value
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground hover:text-foreground"
            }`}
          >
            {m.label}
          </button>
        ))}
        <span className="ml-auto font-mono text-[11px] text-muted-foreground">
          ARIMA RMSE {data.validation.arima_rmse_pct.toFixed(1)}% · LSTM{" "}
          {data.validation.lstm_rmse_pct.toFixed(1)}%
        </span>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={combined} margin={{ left: 8, right: 8, top: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="fg-actual" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.25} />
              <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="fg-forecast" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--chart-2, 142 70% 45%))" stopOpacity={0.3} />
              <stop offset="95%" stopColor="hsl(var(--chart-2, 142 70% 45%))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v: number) => (v === 0 ? "Today" : `D${v}`)}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v: number) => `₹${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`}
            width={52}
          />
          <Tooltip
            formatter={(value: number, name: string) => [formatINR(value), name]}
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine x={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 2" />

          <Area
            type="monotone"
            dataKey="actual"
            name="Actual"
            stroke="hsl(var(--primary))"
            fill="url(#fg-actual)"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
          />
          <Area
            type="monotone"
            dataKey="forecast"
            name="Forecast"
            stroke="hsl(142, 70%, 45%)"
            fill="url(#fg-forecast)"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            dot={false}
            connectNulls={false}
          />
          {mode === "arima" && (
            <>
              <Area
                type="monotone"
                dataKey="ci_hi"
                name="90% CI upper"
                stroke="hsl(142, 70%, 45%)"
                fill="none"
                strokeWidth={0.5}
                strokeDasharray="2 4"
                dot={false}
                connectNulls={false}
              />
              <Area
                type="monotone"
                dataKey="ci_lo"
                name="90% CI lower"
                stroke="hsl(142, 70%, 45%)"
                fill="none"
                strokeWidth={0.5}
                strokeDasharray="2 4"
                dot={false}
                connectNulls={false}
              />
            </>
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
