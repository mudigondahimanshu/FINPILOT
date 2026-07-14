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

  overview: () => authFetch<Overview>("/overview"),

  budgets: {
    list: () => authFetch<Budget[]>("/budgets"),
    categories: () => authFetch<Category[]>("/budgets/categories"),
    create: (body: BudgetCreate) =>
      authFetch<Budget>("/budgets", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<Omit<BudgetCreate, "category_id">>) =>
      authFetch<Budget>(`/budgets/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id: string) => authFetch<void>(`/budgets/${id}`, { method: "DELETE" }),
    status: () => authFetch<BudgetStatus[]>("/transactions/summary/budgets"),
  },

  goals: {
    list: () => authFetch<Goal[]>("/goals"),
    create: (body: GoalCreate) =>
      authFetch<Goal>("/goals", { method: "POST", body: JSON.stringify(body) }),
    update: (id: string, body: Partial<GoalCreate>) =>
      authFetch<Goal>(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    contribute: (id: string, amount: number) =>
      authFetch<Goal>(`/goals/${id}/contribute`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      }),
    delete: (id: string) => authFetch<void>(`/goals/${id}`, { method: "DELETE" }),
  },

  subscriptions: () => authFetch<SubscriptionsResult>("/subscriptions"),
};

// ── Budget / goal / subscription types ───────────────────────────────────────

export interface Budget {
  id: string;
  category_id: string;
  category_name: string;
  amount: string;
  period: string;
  alert_threshold: string;
}

export interface BudgetCreate {
  category_id: string;
  amount: number;
  period?: string;
  alert_threshold?: number;
}

export interface Goal {
  id: string;
  name: string;
  icon: string;
  target_amount: string;
  saved_amount: string;
  target_date: string | null;
  progress_pct: number;
  projected_completion: string | null;
  monthly_needed: string | null;
}

export interface GoalCreate {
  name: string;
  icon?: string;
  target_amount: number;
  saved_amount?: number;
  target_date?: string | null;
}

export interface Subscription {
  name: string;
  avg_amount: number;
  last_amount: number;
  price_change_pct: number;
  cadence: string;
  occurrences: number;
  last_date: string;
  next_due: string;
  monthly_equivalent: number;
  active: boolean;
}

export interface SubscriptionsResult {
  subscriptions: Subscription[];
  active_count: number;
  monthly_total: number;
  price_increases: Subscription[];
}

export interface Overview {
  this_month: { income: number; expenses: number; net: number };
  last_month: { income: number; expenses: number; net: number };
  all_time: { income: number; expenses: number; savings_rate: number };
  by_category: Array<{ name: string; total: number; color: string }>;
  monthly_trend: Array<{ month: string; income: number; expenses: number }>;
  daily_spend_30d: number[];
  budgets: Array<{
    category: string;
    budget: number;
    spent: number;
    utilisation: number;
    over: boolean;
  }>;
  goals: Array<{
    name: string;
    icon: string;
    target: number;
    saved: number;
    progress_pct: number;
  }>;
  subscriptions: {
    active_count: number;
    monthly_total: number;
    upcoming: Subscription[];
    price_increases: Subscription[];
  };
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
  personalized?: boolean;
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
