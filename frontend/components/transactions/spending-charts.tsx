"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type SpendingSummary } from "@/lib/api";
import { formatINR } from "@/lib/utils";

interface Props {
  summary: SpendingSummary;
}

const FALLBACK_COLORS = [
  "#6366F1", "#F59E0B", "#3B82F6", "#EC4899",
  "#8B5CF6", "#10B981", "#06B6D4", "#EF4444",
];

function fmt(v: string | number) {
  return formatINR(Math.abs(Number(v)));
}

function CustomPieTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: "hsl(0 0% 10%)",
        border: "1px solid hsl(0 0% 16%)",
        borderRadius: 8,
        padding: "8px 12px",
      }}>
        <div style={{ color: "#ffffff", fontSize: 13, fontWeight: 500 }}>
          {payload[0].name}
        </div>
        <div style={{ color: "#ffffff", fontSize: 12, marginTop: 4 }}>
          {fmt(payload[0].value)}
        </div>
      </div>
    );
  }
  return null;
}

function CustomBarTooltip({ active, payload, label }: any) {
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
            <span style={{ color: entry.color }}>{entry.name}:</span> {fmt(entry.value)}
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export function SpendingCharts({ summary }: Props) {
  // Only expense categories (total < 0) for the donut.
  const donutData = summary.by_category
    .filter((c) => Number(c.total) < 0)
    .map((c, i) => ({
      name: c.category_name,
      value: Math.abs(Number(c.total)),
      color: c.category_color || FALLBACK_COLORS[i % FALLBACK_COLORS.length]!,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  const trendData = summary.monthly_trend.map((m) => ({
    month: m.month,
    Income: Number(m.income),
    Expenses: Math.abs(Number(m.expenses)),
  }));

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Spending donut */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="mb-4 text-sm font-medium">Spending by category</h3>
        {donutData.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No expense data yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={donutData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={2}
              >
                {donutData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomPieTooltip />} />
              <Legend
                iconType="circle"
                iconSize={8}
                formatter={(value) => <span className="text-xs text-muted-foreground">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Monthly trend bar chart */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="mb-4 text-sm font-medium">Monthly trend</h3>
        {trendData.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No trend data yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={trendData} barSize={14} barGap={4}>
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(0 0% 60%)" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: "hsl(0 0% 60%)" }} axisLine={false} tickLine={false} width={50} />
              <Tooltip content={<CustomBarTooltip />} />
              <Legend iconType="circle" iconSize={8} formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
              <Bar dataKey="Income" fill="#22C55E" radius={[3, 3, 0, 0]} />
              <Bar dataKey="Expenses" fill="#EF4444" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
