"use client";

import * as React from "react";
import Link from "next/link";
import { api, type Overview, type Transaction } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { formatINR } from "@/lib/utils";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Repeat,
  Loader2,
  PiggyBank,
  Target,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// ── Building blocks ───────────────────────────────────────────────────────────

function DeltaChip({ now, before }: { now: number; before: number }) {
  if (before === 0) return null;
  const pct = ((now - before) / Math.abs(before)) * 100;
  const up = pct >= 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-mono text-[10px] ${
        up ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
      }`}
    >
      {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
      {Math.abs(pct).toFixed(0)}% vs last month
    </span>
  );
}

/** Hero band: net cash flow this month over the 30-day spending pulse. */
function CashFlowHero({ data }: { data: Overview }) {
  const net = data.this_month.net;
  const spark = data.daily_spend_30d.map((v, i) => ({ day: i, spend: v }));
  const hasSpark = spark.some((p) => p.spend > 0);

  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-card">
      {hasSpark && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 opacity-40">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={spark} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="pulse" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366F1" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="spend"
                stroke="#6366F1"
                strokeWidth={1.5}
                fill="url(#pulse)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="relative grid gap-6 p-6 sm:grid-cols-[1fr_auto] sm:items-end">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            Net cash flow · this month
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <span
              className={`tabular text-4xl font-semibold sm:text-5xl ${
                net >= 0 ? "text-success" : "text-destructive"
              }`}
            >
              {net >= 0 ? "+" : "−"}
              {formatINR(Math.abs(net))}
            </span>
            <DeltaChip now={net} before={data.last_month.net} />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            The line behind this number is your last 30 days of spending.
          </p>
        </div>

        <dl className="grid grid-cols-3 gap-6 text-right sm:gap-8">
          {[
            { label: "In", value: data.this_month.income, cls: "text-success" },
            { label: "Out", value: data.this_month.expenses, cls: "text-destructive" },
            {
              label: "Saved (all time)",
              value: data.all_time.savings_rate * 100,
              cls: "text-primary",
              isPct: true,
            },
          ].map(({ label, value, cls, isPct }) => (
            <div key={label}>
              <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</dt>
              <dd className={`tabular mt-1 text-lg font-semibold ${cls}`}>
                {isPct ? `${value.toFixed(0)}%` : formatINR(value)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

function PanelHeader({
  icon: Icon,
  title,
  href,
  linkLabel,
}: {
  icon: React.ElementType;
  title: string;
  href: string;
  linkLabel: string;
}) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <Link href={href} className="flex items-center gap-1 text-xs text-primary hover:underline">
        {linkLabel} <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

function BudgetsPanel({ budgets }: { budgets: Overview["budgets"] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <PanelHeader icon={PiggyBank} title="Budgets" href="/budgets" linkLabel="Manage" />
      {budgets.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No budgets yet. Set one to keep a category in check.
        </p>
      ) : (
        <div className="space-y-3.5">
          {budgets.slice(0, 5).map((b) => {
            const pct = Math.min(100, b.utilisation * 100);
            const color = b.over ? "#EF4444" : pct > 80 ? "#F59E0B" : "#22C55E";
            return (
              <div key={b.category} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="max-w-[140px] truncate font-medium">{b.category}</span>
                  <span className="tabular ml-2 text-muted-foreground">
                    {formatINR(b.spent)} / {formatINR(b.budget)}
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
          })}
        </div>
      )}
    </div>
  );
}

function GoalsPanel({ goals }: { goals: Overview["goals"] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <PanelHeader icon={Target} title="Goals" href="/goals" linkLabel="All goals" />
      {goals.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Nothing saved for yet. Create a goal and watch it fill up.
        </p>
      ) : (
        <div className="space-y-3.5">
          {goals.slice(0, 4).map((g) => (
            <div key={g.name} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="max-w-[140px] truncate font-medium">{g.name}</span>
                <span className="tabular ml-2 text-muted-foreground">
                  {g.progress_pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-700"
                  style={{ width: `${Math.min(100, g.progress_pct)}%` }}
                />
              </div>
              <p className="tabular text-[11px] text-muted-foreground">
                {formatINR(g.saved)} of {formatINR(g.target)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SubscriptionsPanel({ subs }: { subs: Overview["subscriptions"] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <PanelHeader
        icon={Repeat}
        title="Subscriptions"
        href="/subscriptions"
        linkLabel="Review"
      />
      {subs.active_count === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No recurring payments detected yet.
        </p>
      ) : (
        <>
          <div className="mb-3 flex items-baseline justify-between rounded-md bg-secondary/50 px-3 py-2">
            <span className="text-xs text-muted-foreground">{subs.active_count} active</span>
            <span className="tabular text-sm font-semibold">
              ₹{subs.monthly_total.toLocaleString("en-IN")}/mo
            </span>
          </div>
          <ul className="space-y-2">
            {subs.upcoming.slice(0, 4).map((s) => (
              <li key={s.name} className="flex items-center justify-between text-xs">
                <span className="max-w-[140px] truncate">{s.name}</span>
                <span className="tabular text-muted-foreground">
                  {new Date(s.next_due).toLocaleDateString("en-IN", {
                    day: "2-digit",
                    month: "short",
                  })}{" "}
                  · {formatINR(s.avg_amount)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

const chartTooltip = {
  contentStyle: {
    backgroundColor: "hsl(0 0% 10%)",
    border: "1px solid hsl(0 0% 16%)",
    borderRadius: 8,
    fontSize: 12,
  },
  itemStyle: { color: "hsl(0 0% 96%)" },
  labelStyle: { color: "hsl(0 0% 60%)" },
} as const;

function TrendChart({ trend }: { trend: Overview["monthly_trend"] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold">Income vs expenses · 6 months</h3>
      {trend.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No history yet.</p>
      ) : (
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trend} barGap={2}>
              <XAxis
                dataKey="month"
                tick={{ fontSize: 11, fill: "hsl(0 0% 60%)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis hide />
              <Tooltip
                {...chartTooltip}
                formatter={(v: number, key: string) => [formatINR(v), key]}
                cursor={{ fill: "hsl(0 0% 14%)" }}
              />
              <Bar dataKey="income" fill="#22C55E" radius={[3, 3, 0, 0]} />
              <Bar dataKey="expenses" fill="#EF4444" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function CategoryChart({ cats }: { cats: Overview["by_category"] }) {
  const spend = cats
    .filter((c) => c.total < 0)
    .map((c) => ({ ...c, value: Math.abs(c.total) }));
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold">Where the money goes</h3>
      {spend.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No spending yet.</p>
      ) : (
        <div className="flex items-center gap-4">
          <div className="h-52 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={spend}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="60%"
                  outerRadius="90%"
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {spend.map((c) => (
                    <Cell key={c.name} fill={c.color} />
                  ))}
                </Pie>
                <Tooltip {...chartTooltip} formatter={(v: number) => formatINR(v)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="w-40 space-y-1.5">
            {spend.slice(0, 6).map((c) => (
              <li key={c.name} className="flex items-center gap-2 text-xs">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: c.color }} />
                <span className="flex-1 truncate text-muted-foreground">{c.name}</span>
                <span className="tabular">{formatINR(c.value)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.full_name?.split(" ")[0] ?? "there";

  const [data, setData] = React.useState<Overview | null>(null);
  const [recent, setRecent] = React.useState<Transaction[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    async function load() {
      try {
        const [ov, txns] = await Promise.all([
          api.overview(),
          api.transactions.list({ page: 1, page_size: 5 }),
        ]);
        setData(ov);
        setRecent(txns.items);
      } catch {
        // Backend may not be reachable during static preview.
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6" style={{ animation: "rise 450ms ease-out both" }}>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back, {name}.</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Everything about your money, on one page.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
        </div>
      ) : data ? (
        <>
          <CashFlowHero data={data} />

          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            <BudgetsPanel budgets={data.budgets} />
            <GoalsPanel goals={data.goals} />
            <SubscriptionsPanel subs={data.subscriptions} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <TrendChart trend={data.monthly_trend} />
            <CategoryChart cats={data.by_category} />
          </div>

          {/* Recent transactions */}
          <div className="rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h3 className="text-sm font-semibold">Recent transactions</h3>
              <Link
                href="/transactions"
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            {recent.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No transactions yet. Add one or import a CSV from the Spending page.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {recent.map((t) => (
                  <li key={t.id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <p className="max-w-xs truncate text-sm font-medium">{t.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(t.date).toLocaleDateString("en-IN", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        })}
                        {t.category && (
                          <span
                            className="ml-2 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                            style={{
                              backgroundColor: `${t.category.color}20`,
                              color: t.category.color,
                            }}
                          >
                            {t.category.name}
                          </span>
                        )}
                      </p>
                    </div>
                    <span
                      className={`tabular text-sm font-semibold ${
                        Number(t.amount) >= 0 ? "text-success" : "text-destructive"
                      }`}
                    >
                      {Number(t.amount) >= 0 ? "+" : "−"}
                      {formatINR(Math.abs(Number(t.amount)))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : (
        <p className="py-20 text-center text-sm text-muted-foreground">
          Couldn&rsquo;t reach the server. Refresh to try again.
        </p>
      )}
    </div>
  );
}
