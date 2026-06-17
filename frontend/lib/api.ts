// Thin typed client for the FastAPI backend.
// Base URLs come from env (NEXT_PUBLIC_*). No secrets here.

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

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    credentials: "include",
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, detail || res.statusText);
  }

  return (await res.json()) as T;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/health"),
};
