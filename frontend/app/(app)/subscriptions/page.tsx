"use client";

import * as React from "react";
import { api, type Subscription, type SubscriptionsResult } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { AlertCircle, ArrowUpRight, Repeat, Loader2 } from "lucide-react";

function CadenceChip({ cadence }: { cadence: string }) {
  return (
    <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
      {cadence}
    </span>
  );
}

function Row({ s }: { s: Subscription }) {
  const nextDue = new Date(s.next_due);
  const daysAway = Math.round((nextDue.getTime() - Date.now()) / 86_400_000);
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3">
        <p className="text-sm font-medium">{s.name}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {s.occurrences} charges seen · last{" "}
          {new Date(s.last_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
        </p>
      </td>
      <td className="px-4 py-3">
        <CadenceChip cadence={s.cadence} />
      </td>
      <td className="tabular px-4 py-3 text-right text-sm">
        {formatINR(s.avg_amount)}
        {s.price_change_pct >= 5 && (
          <span className="ml-1.5 inline-flex items-center gap-0.5 rounded-full bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-500">
            <ArrowUpRight className="h-3 w-3" /> {s.price_change_pct}%
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right text-xs text-muted-foreground">
        {s.active ? (
          daysAway <= 0 ? (
            <span className="font-medium text-warning">due now</span>
          ) : (
            <>
              in {daysAway}d ·{" "}
              {nextDue.toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
            </>
          )
        ) : (
          <span className="text-muted-foreground/60">inactive</span>
        )}
      </td>
      <td className="tabular hidden px-4 py-3 text-right text-sm text-muted-foreground sm:table-cell">
        {formatINR(s.monthly_equivalent)}/mo
      </td>
    </tr>
  );
}

export default function SubscriptionsPage() {
  const [data, setData] = React.useState<SubscriptionsResult | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .subscriptions()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load subscriptions"))
      .finally(() => setLoading(false));
  }, []);

  const active = data?.subscriptions.filter((s) => s.active) ?? [];
  const inactive = data?.subscriptions.filter((s) => !s.active) ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6" style={{ animation: "rise 450ms ease-out both" }}>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Subscriptions</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Recurring payments detected from your transactions — cadence, next charge, and price
          creep, nothing to configure.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
        </div>
      ) : error ? (
        <p
          className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          <AlertCircle className="h-4 w-4" /> {error}
        </p>
      ) : !data || data.subscriptions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border py-16 text-center">
          <Repeat className="mx-auto h-8 w-8 text-muted-foreground/50" />
          <p className="mt-3 text-sm text-muted-foreground">
            No recurring payments detected yet. They&rsquo;ll appear automatically once a merchant
            charges you in two different months.
          </p>
        </div>
      ) : (
        <>
          {/* Monthly cost hero */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                Monthly cost
              </p>
              <p className="tabular mt-2 text-3xl font-semibold text-primary">
                {formatINR(data.monthly_total)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                ≈ {formatINR(data.monthly_total * 12)} a year
              </p>
            </div>
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                Active
              </p>
              <p className="tabular mt-2 text-3xl font-semibold">{data.active_count}</p>
              <p className="mt-1 text-xs text-muted-foreground">recurring merchants</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                Price increases
              </p>
              <p
                className={`tabular mt-2 text-3xl font-semibold ${
                  data.price_increases.length ? "text-warning" : "text-success"
                }`}
              >
                {data.price_increases.length}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {data.price_increases.length
                  ? data.price_increases.map((p) => p.name).join(", ")
                  : "nothing crept up"}
              </p>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-lg border border-border bg-card">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Merchant</th>
                  <th className="px-4 py-3 font-medium">Cadence</th>
                  <th className="px-4 py-3 text-right font-medium">Amount</th>
                  <th className="px-4 py-3 text-right font-medium">Next charge</th>
                  <th className="hidden px-4 py-3 text-right font-medium sm:table-cell">
                    Monthly cost
                  </th>
                </tr>
              </thead>
              <tbody>
                {active.map((s) => (
                  <Row key={s.name} s={s} />
                ))}
                {inactive.map((s) => (
                  <Row key={s.name} s={s} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
