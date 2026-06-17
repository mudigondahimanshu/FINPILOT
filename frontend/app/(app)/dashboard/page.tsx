"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { formatINR } from "@/lib/utils";
import { Bot, LineChart, ShieldCheck, Wallet } from "lucide-react";

const placeholders = [
  {
    icon: Wallet,
    label: "Paper balance",
    value: formatINR(100000),
    note: "Virtual starting capital",
  },
  {
    icon: LineChart,
    label: "30-day forecast",
    value: "—",
    note: "Lands in Phase 1.3",
  },
  {
    icon: Bot,
    label: "Copilot",
    value: "Idle",
    note: "Grounded Q&A — Phase 1.4",
  },
  {
    icon: ShieldCheck,
    label: "Fraud guard",
    value: "Armed",
    note: "Real-time monitoring",
  },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.full_name?.split(" ")[0] ?? "there";

  return (
    <div
      className="mx-auto max-w-5xl"
      style={{ animation: "rise 450ms ease-out both" }}
    >
      <h1 className="text-2xl font-semibold tracking-tight">
        Welcome, {name}.
      </h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Your copilot is set up. Modules unlock as the build progresses.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {placeholders.map(({ icon: Icon, label, value, note }) => (
          <div
            key={label}
            className="rounded-lg border border-border bg-card p-5"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {label}
              </span>
              <Icon className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-3 text-2xl font-semibold tabular">{value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{note}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 rounded-lg border border-dashed border-border p-10 text-center">
        <p className="text-sm text-muted-foreground">
          Spending insights, paper-trading desk, and the explainable copilot
          render here in the next phases.
        </p>
      </div>
    </div>
  );
}
