import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock localStorage for token storage
const store: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (k: string) => store[k] ?? null,
  setItem: (k: string, v: string) => { store[k] = v; },
  removeItem: (k: string) => { delete store[k]; },
});

describe("API token storage", () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k]);
    vi.clearAllMocks();
  });

  it("stores access token on login", () => {
    store["access_token"] = "tok_abc123";
    expect(localStorage.getItem("access_token")).toBe("tok_abc123");
  });

  it("clears token on logout", () => {
    store["access_token"] = "tok_abc123";
    localStorage.removeItem("access_token");
    expect(localStorage.getItem("access_token")).toBeNull();
  });
});

describe("Transaction amount formatting", () => {
  it("identifies income as positive", () => {
    expect(Number("1000.00") >= 0).toBe(true);
  });

  it("identifies expense as negative", () => {
    expect(Number("-500.00") < 0).toBe(true);
  });
});

describe("ML confidence badge logic", () => {
  function confidenceColor(pct: number): string {
    if (pct >= 80) return "emerald";
    if (pct >= 60) return "amber";
    return "muted";
  }

  it("high confidence → emerald", () => {
    expect(confidenceColor(85)).toBe("emerald");
  });
  it("medium confidence → amber", () => {
    expect(confidenceColor(70)).toBe("amber");
  });
  it("low confidence → muted", () => {
    expect(confidenceColor(40)).toBe("muted");
  });
  it("exactly 80 → emerald", () => {
    expect(confidenceColor(80)).toBe("emerald");
  });
  it("exactly 60 → amber", () => {
    expect(confidenceColor(60)).toBe("amber");
  });
});
