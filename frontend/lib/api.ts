// Thin typed client for the FastAPI backend.
// Base URLs come from env (NEXT_PUBLIC_*). No secrets here.
//
// Auth model: the access token lives in memory only (never localStorage, so it
// can't be exfiltrated by XSS-readable storage). The refresh token rides in an
// httpOnly, SameSite=Strict cookie the browser sends automatically. authFetch
// attaches the bearer and, on a 401, silently refreshes once and retries.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── In-memory access token ───────────────────────────────────────────────────
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

async function parseError(res: Response): Promise<string> {
  // FastAPI sends `{ "detail": "..." }`; fall back to raw text / status.
  const text = await res.text().catch(() => "");
  if (!text) return res.statusText;
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return text;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "include",
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Coalesce concurrent refreshes into one in-flight request.
let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await apiFetch<AuthResponse>("/auth/refresh", {
          method: "POST",
        });
        setAccessToken(res.access_token);
        return res.access_token;
      } catch {
        setAccessToken(null);
        return null;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

/** Like apiFetch, but bearer-authenticated with one transparent refresh-retry. */
export async function authFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const withAuth = (token: string | null): RequestInit => ({
    ...init,
    headers: {
      ...init?.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  try {
    return await apiFetch<T>(path, withAuth(accessToken));
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      const fresh = await refreshAccessToken();
      if (fresh) return apiFetch<T>(path, withAuth(fresh));
    }
    throw err;
  }
}

// ── Types (mirror backend Pydantic schemas) ─────────────────────────────────
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  auth_provider: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

// ── Transaction types ────────────────────────────────────────────────────────
export interface Category {
  id: string;
  name: string;
  icon: string;
  color: string;
  is_system: boolean;
}

export interface Transaction {
  id: string;
  date: string;
  amount: string;
  currency: string;
  description: string;
  notes: string | null;
  source: string;
  merchant: string | null;
  is_recurring: boolean | null;
  category_id: string | null;
  account_id: string | null;
  category: Category | null;
  ml_confidence: number | null;
  ml_category_override: boolean | null;
  created_at: string;
}

export interface TransactionPage {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface TransactionCreate {
  date: string;
  amount: number;
  currency?: string;
  description: string;
  notes?: string;
  category_id?: string;
  source?: string;
}

export interface SpendingSummary {
  by_category: Array<{
    category_id: string | null;
    category_name: string;
    category_color: string;
    total: string;
    count: number;
  }>;
  monthly_trend: Array<{
    month: string;
    income: string;
    expenses: string;
    net: string;
  }>;
  total_income: string;
  total_expenses: string;
  savings_rate: string;
}

export interface BudgetStatus {
  budget_id: string;
  category_name: string;
  period: string;
  budget_amount: string;
  spent: string;
  remaining: string;
  utilisation: string;
  alert_threshold: string;
  over_budget: boolean;
}

export interface CsvUploadResult {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface TransactionFilters {
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
  category_id?: string;
  amount_min?: number;
  amount_max?: number;
  search?: string;
}

// ── Endpoint surface ─────────────────────────────────────────────────────────
export const api = {
  health: () => apiFetch<HealthResponse>("/health"),

  auth: {
    register: (body: RegisterPayload) =>
      apiFetch<AuthResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    login: (body: LoginPayload) =>
      apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    refresh: () => refreshAccessToken(),
    me: () => authFetch<User>("/auth/me"),
    logout: () => authFetch<void>("/auth/logout", { method: "POST" }),
    googleLoginUrl: () => `${API_URL}/auth/google/login`,
  },

  transactions: {
    list: (filters: TransactionFilters = {}) => {
      const p = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
      });
      return authFetch<TransactionPage>(`/transactions?${p}`);
    },
    create: (body: TransactionCreate) =>
      authFetch<Transaction>("/transactions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    update: (id: string, body: Partial<TransactionCreate>) =>
      authFetch<Transaction>(`/transactions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      authFetch<void>(`/transactions/${id}`, { method: "DELETE" }),
    uploadCsv: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return authFetch<CsvUploadResult>("/transactions/import/csv", {
        method: "POST",
        headers: {},  // let browser set multipart boundary
        body: form,
      });
    },
    summary: (params: { date_from?: string; date_to?: string } = {}) => {
      const p = new URLSearchParams();
      if (params.date_from) p.set("date_from", params.date_from);
      if (params.date_to) p.set("date_to", params.date_to);
      return authFetch<SpendingSummary>(`/transactions/summary/spending?${p}`);
    },
    budgets: () => authFetch<BudgetStatus[]>("/transactions/summary/budgets"),
    recurring: () => authFetch<Record<string, unknown>[]>("/transactions/summary/recurring"),
  },

  market: {
    search: (q: string, limit = 10) =>
      authFetch<TickerResult[]>(`/market/search?q=${encodeURIComponent(q)}&limit=${limit}`),
    quote: (symbol: string) => authFetch<Quote>(`/market/quote/${symbol}`),
    ohlc: (symbol: string, interval = "1d", period = "1y", withMa = true) =>
      authFetch<OhlcResponse>(`/market/ohlc/${symbol}?interval=${interval}&period=${period}&with_ma=${withMa}`),
    fundamentals: (symbol: string) => authFetch<Fundamentals>(`/market/fundamentals/${symbol}`),
    watchlist: () => authFetch<WatchlistItem[]>("/market/watchlist"),
    addWatch: (symbol: string, exchange = "NSE") =>
      authFetch<WatchlistItem>(`/market/watchlist/${symbol}?exchange=${exchange}`, { method: "POST" }),
    removeWatch: (symbol: string) =>
      authFetch<void>(`/market/watchlist/${symbol}`, { method: "DELETE" }),
  },

  portfolio: {
    summary: () => authFetch<PortfolioSummary>("/portfolio/summary"),
    placeOrder: (body: TradeCreate) =>
      authFetch<TradeRead>("/portfolio/order", { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }),
    trades: (limit = 50, offset = 0) =>
      authFetch<TradeRead[]>(`/portfolio/trades?limit=${limit}&offset=${offset}`),
    orderBook: (symbol: string, levels = 5) =>
      authFetch<OrderBookDepth>(`/portfolio/orderbook/${symbol}?levels=${levels}`),
  },

  optimizer: {
    efficientFrontier: (body: OptimizeRequest) =>
      authFetch<EfficientFrontierResult>("/optimizer/efficient-frontier", {
        method: "POST",
        body: JSON.stringify(body),
        headers: { "Content-Type": "application/json" },
      }),
    riskScore: (symbols: string[], weights: number[]) =>
      authFetch<{ risk_score: number; label: string }>("/optimizer/risk-score", {
        method: "POST",
        body: JSON.stringify({ symbols, weights }),
        headers: { "Content-Type": "application/json" },
      }),
  },
};

// ── Market types ──────────────────────────────────────────────────────────────

export interface TickerResult {
  symbol: string;
  name: string;
  exchange: string;
}

export interface Quote {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  market_cap: number | null;
  currency: string;
  exchange: string;
  fetched_at: string;
  error?: string;
}

export interface OhlcCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OhlcResponse {
  candles: OhlcCandle[];
  sma20?: (number | null)[];
  sma50?: (number | null)[];
  ema20?: (number | null)[];
}

export interface Fundamentals {
  longName: string | null;
  sector: string | null;
  industry: string | null;
  country: string | null;
  marketCap: number | null;
  trailingPE: number | null;
  forwardPE: number | null;
  priceToBook: number | null;
  dividendYield: number | null;
  beta: number | null;
  fiftyTwoWeekHigh: number | null;
  fiftyTwoWeekLow: number | null;
  longBusinessSummary: string | null;
}

export interface WatchlistItem {
  id: string;
  symbol: string;
  exchange: string;
  added_at: string;
}

// ── Portfolio types ───────────────────────────────────────────────────────────

export interface Holding {
  symbol: string;
  quantity: string;
  avg_cost: string;
  current_price: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_pct: string | null;
  market_value: string | null;
}

export interface PortfolioData {
  id: string;
  name: string;
  cash_balance: string;
  currency: string;
  created_at: string;
}

export interface PortfolioSummary {
  portfolio: PortfolioData;
  holdings: Holding[];
  total_invested: string;
  market_value: string | null;
  unrealized_pnl: string | null;
  realized_pnl: string;
  total_pnl: string | null;
}

export interface TradeCreate {
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price?: number;
  notes?: string;
}

export interface TradeRead {
  id: string;
  portfolio_id: string;
  symbol: string;
  exchange: string;
  side: string;
  quantity: string;
  price: string;
  cash_delta: string;
  status: string;
  notes: string | null;
  executed_at: string;
}

export interface OrderBookDepth {
  symbol: string;
  bids: [number, number][];
  asks: [number, number][];
  best_bid: number | null;
  best_ask: number | null;
}

// ── Optimizer types ───────────────────────────────────────────────────────────

export interface OptimizeRequest {
  symbols: string[];
  period?: string;
  n_portfolios?: number;
  risk_free_rate?: number;
}

export interface FrontierPoint {
  weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe: number;
}

export interface Allocation {
  weights: Record<string, number>;
  expected_annual_return: number;
  annual_volatility: number;
  sharpe_ratio?: number;
}

export interface EfficientFrontierResult {
  symbols: string[];
  frontier: FrontierPoint[];
  max_sharpe: Allocation;
  min_volatility: Allocation;
  presets: {
    conservative: Allocation;
    moderate: Allocation;
    aggressive: Allocation;
  };
  risk_free_rate: number;
}

// ── ML / AI Brain types ───────────────────────────────────────────────────────

export interface ForecastValidation {
  arima_rmse: number;
  lstm_rmse: number;
  arima_rmse_pct: number;
  lstm_rmse_pct: number;
}

export interface SpendForecast {
  horizon_days: number;
  arima: number[];
  arima_ci_lower: number[];
  arima_ci_upper: number[];
  lstm: number[];
  ensemble: number[];
  validation: ForecastValidation;
}

export interface SentimentArticle {
  title: string;
  url: string;
  published: string;
  source: string;
  score: number;
  label: "Bullish" | "Bearish" | "Neutral";
}

export interface SentimentResult {
  symbol: string;
  overall_score: number;
  overall_label: "Bullish" | "Bearish" | "Neutral";
  articles: SentimentArticle[];
  cached: boolean;
}

export interface CopilotSource {
  id: string;
  content: string;
  similarity: number;
}

export interface CopilotResponse {
  answer: string;
  sources: CopilotSource[];
  reasoning?: string;
  model: string;
}

export interface FraudResult {
  isolation_forest: { anomaly_score: number; is_anomaly: boolean }[];
  velocity_flags: { description: string; signal: string; count: number }[];
  connected_components: string[][];
  cycles: string[][];
}

export interface ClassifyResult {
  category: string;
  confidence: number;
  method: string;
}

// ── ML API functions ──────────────────────────────────────────────────────────

export function fetchSpendForecast(days = 90, horizon = 30): Promise<SpendForecast> {
  return authFetch<SpendForecast>(`/ml/forecast/spending?days=${days}&horizon=${horizon}`);
}

export function fetchStockSentiment(symbol: string): Promise<SentimentResult> {
  return authFetch<SentimentResult>(`/ml/sentiment/${encodeURIComponent(symbol)}`);
}

export function copilotChat(
  question: string,
  history: { role: string; content: string }[] = [],
): Promise<CopilotResponse> {
  return authFetch<CopilotResponse>("/ml/copilot/chat", {
    method: "POST",
    body: JSON.stringify({ question, history }),
  });
}

export function fetchFraudAnalysis(): Promise<FraudResult> {
  return authFetch<FraudResult>("/ml/fraud");
}

export function classifyTransaction(
  description: string,
  amount: number,
  date: string,
): Promise<ClassifyResult> {
  return authFetch<ClassifyResult>("/ml/classify", {
    method: "POST",
    body: JSON.stringify({ description, amount, date }),
  });
}

export function submitCategoryOverride(
  transactionId: string,
  correctedCategory: string,
  description: string,
  amount: number,
  originalCategory?: string,
): Promise<{ status: string; category: string }> {
  return authFetch("/ml/classify/override", {
    method: "POST",
    body: JSON.stringify({
      transaction_id: transactionId,
      corrected_category: correctedCategory,
      description,
      amount,
      original_category: originalCategory ?? null,
    }),
  });
}

export function submitCopilotFeedback(
  question: string,
  answer: string,
  thumbsUp: boolean,
): Promise<{ status: string }> {
  return authFetch("/ml/copilot/feedback", {
    method: "POST",
    body: JSON.stringify({ question, answer, thumbs_up: thumbsUp }),
  });
}
