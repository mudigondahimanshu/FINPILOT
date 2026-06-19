"use client";

import * as React from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Brain,
  Loader2,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";
import {
  fetchFraudAnalysis,
  fetchSpendForecast,
  fetchStockSentiment,
  type FraudResult,
  type SentimentResult,
  type SpendForecast,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ForecastChart } from "@/components/ml/forecast-chart";
import { SentimentFeed } from "@/components/ml/sentiment-feed";
import { ChatWidget } from "@/components/ml/chat-widget";

const WATCHLIST_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "NIFTY50.NS"];

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

function FraudSummary({ data }: { data: FraudResult }) {
  const anomalies = data.isolation_forest.filter((r) => r.is_anomaly);
  const hasIssues = anomalies.length > 0 || data.velocity_flags.length > 0 || data.cycles.length > 0;

  if (!hasIssues) {
    return (
      <div className="flex items-center gap-2.5 rounded-md bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-3">
        <ShieldAlert className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        <p className="text-sm text-emerald-700 dark:text-emerald-300">
          No suspicious activity detected in your recent transactions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {anomalies.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-3">
          <AlertTriangle className="h-4 w-4 mt-0.5 text-amber-600 dark:text-amber-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
              {anomalies.length} anomalous transaction{anomalies.length !== 1 ? "s" : ""} detected
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Isolation Forest flagged these as statistical outliers. Review your recent spending.
            </p>
          </div>
        </div>
      )}
      {data.velocity_flags.map((f, i) => (
        <div
          key={i}
          className="flex items-start gap-2.5 rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 px-4 py-3"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 text-red-600 dark:text-red-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-700 dark:text-red-300">
              Velocity alert: {f.description}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{f.count} transactions in window</p>
          </div>
        </div>
      ))}
      {data.cycles.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-md border border-purple-200 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/30 px-4 py-3">
          <AlertTriangle className="h-4 w-4 mt-0.5 text-purple-600 dark:text-purple-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-purple-700 dark:text-purple-300">
              Circular payment cycle detected
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Money may be cycling between {data.cycles[0]?.join(" → ")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function InsightsPage() {
  const [forecast, setForecast] = React.useState<SpendForecast | null>(null);
  const [forecastErr, setForecastErr] = React.useState<string | null>(null);
  const [forecastLoading, setForecastLoading] = React.useState(true);

  const [sentiment, setSentiment] = React.useState<SentimentResult | null>(null);
  const [sentimentErr, setSentimentErr] = React.useState<string | null>(null);
  const [sentimentLoading, setSentimentLoading] = React.useState(false);
  const [sentimentSymbol, setSentimentSymbol] = React.useState(WATCHLIST_SYMBOLS[0]!);

  const [fraud, setFraud] = React.useState<FraudResult | null>(null);
  const [fraudErr, setFraudErr] = React.useState<string | null>(null);
  const [fraudLoading, setFraudLoading] = React.useState(true);

  const loadForecast = React.useCallback(async () => {
    setForecastLoading(true);
    setForecastErr(null);
    try {
      const data = await fetchSpendForecast(90, 30);
      setForecast(data);
    } catch (e) {
      setForecastErr(e instanceof Error ? e.message : "Failed to load forecast");
    } finally {
      setForecastLoading(false);
    }
  }, []);

  const loadSentiment = React.useCallback(
    async (symbol: string) => {
      setSentimentLoading(true);
      setSentimentErr(null);
      try {
        const data = await fetchStockSentiment(symbol);
        setSentiment(data);
      } catch (e) {
        setSentimentErr(e instanceof Error ? e.message : "Failed to load sentiment");
      } finally {
        setSentimentLoading(false);
      }
    },
    [],
  );

  const loadFraud = React.useCallback(async () => {
    setFraudLoading(true);
    setFraudErr(null);
    try {
      const data = await fetchFraudAnalysis();
      setFraud(data);
    } catch (e) {
      setFraudErr(e instanceof Error ? e.message : "Failed to load fraud analysis");
    } finally {
      setFraudLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadForecast();
    void loadFraud();
  }, [loadForecast, loadFraud]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Insights</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            ARIMA + LSTM forecasting · VADER/FinBERT sentiment · RAG copilot · Fraud detection
          </p>
        </div>
      </div>

      {/* 2-column layout */}
      <div className="grid gap-6 lg:grid-cols-2">
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

        {/* AI Copilot */}
        <SectionCard title="AI Copilot" icon={Bot}>
          <ChatWidget />
        </SectionCard>

        {/* Sentiment */}
        <SectionCard
          title="News Sentiment"
          icon={Brain}
          action={
            <div className="flex items-center gap-1.5">
              {WATCHLIST_SYMBOLS.map((sym) => (
                <button
                  key={sym}
                  onClick={() => {
                    setSentimentSymbol(sym);
                    void loadSentiment(sym);
                  }}
                  className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                    sentimentSymbol === sym
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {sym.replace(/\.(NS|BO)$/, "")}
                </button>
              ))}
            </div>
          }
        >
          {sentimentLoading ? (
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : sentimentErr ? (
            <div className="flex h-32 flex-col items-center justify-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              <p className="text-sm text-muted-foreground">{sentimentErr}</p>
            </div>
          ) : sentiment ? (
            <SentimentFeed data={sentiment} />
          ) : (
            <div className="flex h-32 flex-col items-center justify-center gap-2">
              <p className="text-sm text-muted-foreground">
                Select a symbol to load news sentiment.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void loadSentiment(sentimentSymbol)}
              >
                Load {sentimentSymbol.replace(/\.(NS|BO)$/, "")}
              </Button>
            </div>
          )}
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
            <FraudSummary data={fraud} />
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
