"use client";

import * as React from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Check,
  Repeat,
  Loader2,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
  X,
} from "lucide-react";
import {
  api,
  fetchFraudAnalysis,
  fetchSpendForecast,
  setFraudAlertDecision,
  type FraudResult,
  type SpendForecast,
  type SubscriptionsResult,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ForecastChart } from "@/components/ml/forecast-chart";
import { ChatWidget } from "@/components/ml/chat-widget";
import { formatINR } from "@/lib/utils";

function SectionCard({
  title,
  icon: Icon,
  children,
  action,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

function FraudSummary({
  data,
  onDecisionSaved,
}: {
  data: FraudResult;
  onDecisionSaved: () => Promise<void>;
}) {
  const [selectedAlert, setSelectedAlert] = React.useState<FraudResult["anomalous_transactions"][number] | null>(null);
  const [savingDecision, setSavingDecision] = React.useState(false);
  const [decisionError, setDecisionError] = React.useState<string | null>(null);
  const anomalies = data.anomalous_transactions ?? [];
  const activeAnomalies = anomalies.filter((alert) => alert.decision !== "remove");
  const removedAnomalies = anomalies.filter((alert) => alert.decision === "remove");
  const velocityFlags = data.velocity_signals ?? [];
  const cycles = data.graph_cycles ?? [];
  const hasIssues = activeAnomalies.length > 0 || velocityFlags.length > 0 || cycles.length > 0;
  async function saveDecision(decision: "keep" | "remove") {
    if (!selectedAlert) return;
    setSavingDecision(true);
    setDecisionError(null);
    try {
      await setFraudAlertDecision(selectedAlert.id, decision);
      await onDecisionSaved();
      setSelectedAlert(null);
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "Couldn't save your choice");
    } finally {
      setSavingDecision(false);
    }
  }

  return (
    <div className="space-y-2">
      {!hasIssues && (
        <div className="flex items-center gap-2.5 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-800 dark:bg-emerald-950/30">
          <ShieldAlert className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <p className="text-sm text-emerald-700 dark:text-emerald-300">
            No suspicious activity detected in your recent transactions.
          </p>
        </div>
      )}
      {activeAnomalies.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-3">
          <AlertTriangle className="h-4 w-4 mt-0.5 text-amber-600 dark:text-amber-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
              {activeAnomalies.length} anomalous transaction
              {activeAnomalies.length !== 1 ? "s" : ""} detected
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Isolation Forest flagged these as statistical outliers. Review your recent spending.
            </p>
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
              {activeAnomalies.map((txn) => {
                const content = `${txn.description}: ${formatINR(Math.abs(txn.amount))} · score ${txn.anomaly_score.toFixed(2)}`;
                return (
                  <li key={txn.id}>
                    <button
                      type="button"
                      className="group flex w-full cursor-pointer items-center justify-between gap-3 rounded px-1 py-1 text-left hover:bg-amber-100/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:hover:bg-amber-900/30"
                      aria-label={`Review ${txn.description}, ${formatINR(Math.abs(txn.amount))}`}
                      onClick={() => { setSelectedAlert(txn); setDecisionError(null); }}
                    >
                      <span>{content}</span>
                      <span className="shrink-0 rounded border border-primary/30 px-2 py-1 font-medium text-primary underline-offset-2 group-hover:underline">
                        {txn.decision === "keep" ? "Kept · review" : "Review options"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
      {velocityFlags.map((f, i) => (
        <div
          key={i}
          className="flex items-start gap-2.5 rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 px-4 py-3"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 text-red-600 dark:text-red-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-700 dark:text-red-300">
              Velocity alert: {f.merchant}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {f.transactions_in_window} transactions in {f.window_minutes} minutes
            </p>
          </div>
        </div>
      ))}
      {cycles.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-md border border-purple-200 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/30 px-4 py-3">
          <AlertTriangle className="h-4 w-4 mt-0.5 text-purple-600 dark:text-purple-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-purple-700 dark:text-purple-300">
              Circular payment cycle detected
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Money may be cycling between {cycles[0]?.join(" → ")}
            </p>
          </div>
        </div>
      )}
      {removedAnomalies.length > 0 && (
        <div className="rounded-md border border-border bg-secondary/30 px-4 py-3">
          <p className="text-xs font-medium text-muted-foreground">
            Removed from suspicious activity by you
          </p>
          <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
            {removedAnomalies.map((alert) => (
              <li key={alert.id}>
                <button
                  type="button"
                  className="text-left underline underline-offset-2 hover:text-foreground"
                  onClick={() => { setSelectedAlert(alert); setDecisionError(null); }}
                >
                  {alert.description}: {formatINR(Math.abs(alert.amount))} · Review choice
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {selectedAlert && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !savingDecision) setSelectedAlert(null);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="fraud-alert-dialog-title"
            className="w-full max-w-md rounded-xl border border-amber-500/40 bg-card p-5 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <h3 id="fraud-alert-dialog-title" className="text-base font-semibold">
                  Review suspicious activity
                </h3>
              </div>
              <button
                type="button"
                aria-label="Close"
                className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                disabled={savingDecision}
                onClick={() => setSelectedAlert(null)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 rounded-md border border-border bg-background/60 p-3">
              <p className="text-sm font-medium">{selectedAlert.description}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {selectedAlert.merchant || "Merchant unavailable"} · {formatINR(Math.abs(selectedAlert.amount))}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {new Date(selectedAlert.date).toLocaleDateString("en-IN")} · anomaly score {selectedAlert.anomaly_score.toFixed(2)}
              </p>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Keep this transaction flagged, or remove it from suspicious activity? The transaction itself will remain in your records.
            </p>
            {decisionError && (
              <p className="mt-3 text-sm text-destructive" role="alert">{decisionError}</p>
            )}
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                disabled={savingDecision}
                onClick={() => void saveDecision("remove")}
              >
                Remove from alerts
              </Button>
              <Button
                disabled={savingDecision}
                onClick={() => void saveDecision("keep")}
              >
                <Check className="h-4 w-4" /> Keep flagged
              </Button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function SubscriptionWatch({ data }: { data: SubscriptionsResult }) {
  if (data.active_count === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        No recurring payments detected yet. Import more transaction history to
        see your subscriptions here.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between rounded-md bg-secondary/50 px-4 py-3">
        <span className="text-sm text-muted-foreground">
          {data.active_count} active subscription{data.active_count !== 1 ? "s" : ""}
        </span>
        <span className="tabular text-sm font-semibold">
          ₹{data.monthly_total.toLocaleString("en-IN")}/mo
        </span>
      </div>
      {data.price_increases.length > 0 ? (
        data.price_increases.map((s) => (
          <div
            key={s.name}
            className="flex items-start gap-2.5 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-3"
          >
            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <div>
              <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
                {s.name} went up {s.price_change_pct}%
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Last charge ₹{s.last_amount.toLocaleString("en-IN")} vs ₹
                {s.avg_amount.toLocaleString("en-IN")} average — worth reviewing.
              </p>
            </div>
          </div>
        ))
      ) : (
        <p className="text-xs text-muted-foreground">
          No price increases detected across your subscriptions.
        </p>
      )}
    </div>
  );
}

export default function InsightsPage() {
  const [forecast, setForecast] = React.useState<SpendForecast | null>(null);
  const [forecastErr, setForecastErr] = React.useState<string | null>(null);
  const [forecastLoading, setForecastLoading] = React.useState(true);

  const [fraud, setFraud] = React.useState<FraudResult | null>(null);
  const [fraudErr, setFraudErr] = React.useState<string | null>(null);
  const [fraudLoading, setFraudLoading] = React.useState(true);

  const [subs, setSubs] = React.useState<SubscriptionsResult | null>(null);
  const [subsErr, setSubsErr] = React.useState<string | null>(null);

  const loadForecast = React.useCallback(async () => {
    setForecastLoading(true);
    setForecastErr(null);
    try {
      setForecast(await fetchSpendForecast(90, 30));
    } catch (e) {
      setForecastErr(e instanceof Error ? e.message : "Failed to load forecast");
    } finally {
      setForecastLoading(false);
    }
  }, []);

  const loadFraud = React.useCallback(async () => {
    setFraudLoading(true);
    setFraudErr(null);
    try {
      setFraud(await fetchFraudAnalysis());
    } catch (e) {
      setFraudErr(e instanceof Error ? e.message : "Failed to load fraud analysis");
    } finally {
      setFraudLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadForecast();
    void loadFraud();
    api.subscriptions().then(setSubs).catch((e) =>
      setSubsErr(e instanceof Error ? e.message : "Failed to load subscriptions"),
    );
  }, [loadForecast, loadFraud]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Insights</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Personal copilot · ARIMA + LSTM forecasting · Fraud detection · Subscription watch
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* AI Copilot — the headline feature, full left column */}
        <SectionCard title="AI Copilot" icon={Bot}>
          <ChatWidget />
        </SectionCard>

        <div className="space-y-6">
          {/* Spend Forecast */}
          <SectionCard
            title="Spending Forecast"
            icon={TrendingUp}
            action={
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => void loadForecast()}>
                <RefreshCw className={`h-3.5 w-3.5 ${forecastLoading ? "animate-spin" : ""}`} />
              </Button>
            }
          >
            {forecastLoading ? (
              <div className="flex h-48 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : forecastErr ? (
              <div className="flex h-48 flex-col items-center justify-center gap-2 text-center">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <p className="text-sm text-muted-foreground">{forecastErr}</p>
                <p className="text-xs text-muted-foreground/70">
                  Need ≥4 days of transaction history to forecast.
                </p>
              </div>
            ) : forecast ? (
              <ForecastChart data={forecast} />
            ) : null}
          </SectionCard>

          {/* Fraud Guard */}
          <SectionCard
            title="Fraud Guard"
            icon={ShieldAlert}
            action={
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => void loadFraud()}>
                <RefreshCw className={`h-3.5 w-3.5 ${fraudLoading ? "animate-spin" : ""}`} />
              </Button>
            }
          >
            {fraudLoading ? (
              <div className="flex h-24 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : fraudErr ? (
              <div className="flex h-24 flex-col items-center justify-center gap-2">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <p className="text-sm text-muted-foreground">{fraudErr}</p>
              </div>
            ) : fraud ? (
              <FraudSummary
                data={fraud}
                onDecisionSaved={loadFraud}
              />
            ) : null}
          </SectionCard>

          {/* Subscription watch */}
          <SectionCard title="Subscription Watch" icon={Repeat}>
            {subsErr ? (
              <p className="py-4 text-center text-sm text-muted-foreground">{subsErr}</p>
            ) : subs ? (
              <SubscriptionWatch data={subs} />
            ) : (
              <div className="flex h-16 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
