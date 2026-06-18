"use client";

import * as React from "react";
import Link from "next/link";
import { api, type SpendingSummary, type BudgetStatus, type Transaction } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { formatINR } from "@/lib/utils";
import {
  ArrowRight,
  Bot,
  Loader2,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { SpendingCharts } from "@/components/transactions/spending-charts";

// ── helpers ──────────────────────────────────────────────────────────────────

function SavingsGauge({ rate }: { rate: number }) {
  const pct = Math.min(100, Math.max(0, rate * 100));
  const color = pct >= 20 ? "#22C55E" : pct >= 10 ? "#F59E0B" : "#EF4444";
  const r = 44;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.75;
  const filled = arc * (pct / 100);
  const dashoffset = arc - filled;

  return (
    <svg viewBox="0 0 100 80" className="w-32" aria-label={`Savings rate ${pct.toFixed(1)}%`}>
      {/* Background arc */}
      <circle
        cx="50" cy="54" r={r}
        fill="none" stroke="hsl(0 0% 16%)" strokeWidth="10"
        strokeDasharray={`${arc} ${circ}`}
        strokeDashoffset={circ * 0.125}
        strokeLinecap="round"
        transform="rotate(180 50 54)"
      />
      {/* Filled arc */}
      <circle
        cx="50" cy="54" r={r}
        fill="none" stroke={color} strokeWidth="10"
        strokeDasharray={`${filled} ${circ}`}
        strokeDashoffset={circ * 0.125}
        strokeLinecap="round"
        transform="rotate(180 50 54)"
        style={{ transition: "stroke-dasharray 800ms ease-out" }}
      />
      <text x="50" y="56" textAnchor="middle" fontSize="15" fontWeight="600" fill={color}>
        {pct.toFixed(1)}%
      </text>
      <text x="50" y="68" textAnchor="middle" fontSize="7" fill="hsl(0 0% 55%)">
        savings rate
      </text>
    </svg>
  );
}

function BudgetBar({ b }: { b: BudgetStatus }) {
  const pct = Math.min(100, Number(b.utilisation) * 100);
  const color = b.over_budget ? "#EF4444" : pct > 80 ? "#F59E0B" : "#22C55E";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium truncate max-w-[140px]">{b.category_name}</span>
        <span className="tabular text-muted-foreground ml-2">
          {formatINR(Number(b.spent))} / {formatINR(Number(b.budget_amount))}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.full_name?.split(" ")[0] ?? "there";

  const [summary, setSummary] = React.useState<SpendingSummary | null>(null);
  const [budgets, setBudgets] = React.useState<BudgetStatus[]>([]);
  const [recent, setRecent] = React.useState<Transaction[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    async function load() {
      try {
        const [sum, bgt, txns] = await Promise.all([
          api.transactions.summary(),
          api.transactions.budgets(),
          api.transactions.list({ page: 1, page_size: 5 }),
        ]);
        setSummary(sum);
        setBudgets(bgt);
        setRecent(txns.items);
      } catch {
        // Backend may not be reachable during static preview.
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const income = summary ? Number(summary.total_income) : 0;
  const expenses = summary ? Math.abs(Number(summary.total_expenses)) : 0;
  const savings = income - expenses;
  const savingsRate = income > 0 ? savings / income : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-8" style={{ animation: "rise 450ms ease-out both" }}>
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back, {name}.</h1>
        <p className="mt-1 text-sm text-muted-foreground">Here&rsquo;s your financial snapshot.</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
        </div>
      ) : (
        <>
          {/* KPI row */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: TrendingUp, label: "Total income", value: formatINR(income), color: "text-success", note: "This period" },
              { icon: TrendingDown, label: "Total expenses", value: formatINR(expenses), color: "text-destructive", note: "This period" },
              { icon: Wallet, label: "Net savings", value: formatINR(Math.abs(savings)), color: savings >= 0 ? "text-success" : "text-destructive", note: savings >= 0 ? "Surplus" : "Deficit" },
              { icon: Bot, label: "Active budgets", value: budgets.length.toString(), color: "text-primary", note: `${budgets.filter(b => b.over_budget).length} over limit` },
            ].map(({ icon: Icon, label, value, color, note }) => (
              <div key={label} className="rounded-lg border border-border bg-card p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
                  <Icon className={`h-4 w-4 ${color}`} />
                </div>
                <p className={`mt-3 text-2xl font-semibold tabular ${color}`}>{summary ? value : "—"}</p>
                <p className="mt-1 text-xs text-muted-foreground">{note}</p>
              </div>
            ))}
          </div>

          {/* Savings gauge + budget bars */}
          <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
            {/* Gauge card */}
            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="mb-4 text-sm font-medium">Savings rate</h3>
              <div className="flex flex-col items-center gap-4">
                <SavingsGauge rate={savingsRate} />
                <div className="w-full space-y-1.5 text-sm">
                  {[
                    { label: "Income", value: formatINR(income), color: "bg-success" },
                    { label: "Expenses", value: formatINR(expenses), color: "bg-destructive" },
                    { label: "Saved", value: formatINR(Math.abs(savings)), color: "bg-primary" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${color}`} />
                      <span className="text-muted-foreground flex-1">{label}</span>
                      <span className="tabular font-medium">{summary ? value : "—"}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Budget progress bars */}
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-medium">Budget utilisation</h3>
                <span className="text-xs text-muted-foreground">Current month</span>
              </div>
              {budgets.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No budgets set yet.</p>
              ) : (
                <div className="space-y-4">
                  {budgets.map((b) => <BudgetBar key={b.budget_id} b={b} />)}
                </div>
              )}
            </div>
          </div>

          {/* Charts */}
          {summary && <SpendingCharts summary={summary} />}

          {/* Recent transactions */}
          <div className="rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h3 className="text-sm font-medium">Recent transactions</h3>
              <Link href="/transactions" className="flex items-center gap-1 text-xs text-primary hover:underline">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            {recent.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No transactions yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {recent.map((t) => (
                  <li key={t.id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <p className="text-sm font-medium truncate max-w-xs">{t.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(t.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                        {t.category && (
                          <span
                            className="ml-2 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                            style={{ backgroundColor: `${t.category.color}20`, color: t.category.color }}
                          >
                            {t.category.name}
                          </span>
                        )}
                      </p>
                    </div>
                    <span className={`tabular text-sm font-semibold ${Number(t.amount) >= 0 ? "text-success" : "text-destructive"}`}>
                      {Number(t.amount) >= 0 ? "+" : "−"}{formatINR(Math.abs(Number(t.amount)))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Coming soon modules */}
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { icon: ShieldCheck, label: "Fraud guard", note: "Real-time anomaly detection — Phase 2.3" },
              { icon: Bot, label: "Copilot Q&A", note: "RAG-powered grounded answers — Phase 2.1" },
            ].map(({ icon: Icon, label, note }) => (
              <div key={label} className="rounded-lg border border-dashed border-border bg-card/40 p-5 opacity-60">
                <div className="flex items-center gap-3">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{note}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
