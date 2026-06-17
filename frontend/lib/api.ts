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
};
