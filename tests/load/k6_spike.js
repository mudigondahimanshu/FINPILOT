/**
 * k6 load test — FinPilot API (Phase 4.4)
 *
 * Scenarios:
 *   1. smoke   — 5 VU, 30s:   sanity check
 *   2. average — 50 VU, 5min: normal production load
 *   3. spike   — ramp to 1000 VU in 30s: stress test
 *
 * Run: k6 run tests/load/k6_spike.js -e BASE_URL=http://localhost:8000
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const TEST_EMAIL = __ENV.TEST_EMAIL || "load@finpilot.test";
const TEST_PASS = __ENV.TEST_PASSWORD || "LoadTest123!";

// Custom metrics
const errorRate = new Rate("errors");
const loginLatency = new Trend("login_latency_ms", true);
const txnLatency = new Trend("txn_list_latency_ms", true);

export const options = {
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: 5,
      duration: "30s",
      tags: { scenario: "smoke" },
    },
    average_load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "1m", target: 50 },
        { duration: "3m", target: 50 },
        { duration: "1m", target: 0 },
      ],
      startTime: "35s",
      tags: { scenario: "average" },
    },
    spike: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 1000 },
        { duration: "1m", target: 1000 },
        { duration: "30s", target: 0 },
      ],
      startTime: "6m",
      tags: { scenario: "spike" },
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],         // < 1% errors
    http_req_duration: ["p(99)<2000"],      // p99 < 2s
    login_latency_ms: ["p(95)<500"],        // login p95 < 500ms
    txn_list_latency_ms: ["p(95)<1000"],    // txn list p95 < 1s
  },
};

let authToken = "";

export function setup() {
  // Register + login once to get a shared token for read-only tests
  const reg = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email: TEST_EMAIL, password: TEST_PASS, full_name: "Load Tester" }),
    { headers: { "Content-Type": "application/json" } },
  );
  // May already exist — that's fine
  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: TEST_EMAIL, password: TEST_PASS }),
    { headers: { "Content-Type": "application/json" } },
  );
  return { token: login.json("access_token") || "" };
}

export default function (data) {
  const token = data.token;
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  // Health check (unauthenticated)
  {
    const res = http.get(`${BASE_URL}/health`);
    check(res, { "health 200": (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  }

  // Login (tests auth throughput)
  {
    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email: TEST_EMAIL, password: TEST_PASS }),
      { headers: { "Content-Type": "application/json" } },
    );
    loginLatency.add(Date.now() - start);
    check(res, { "login 200": (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  }

  // Transaction list (authenticated read)
  {
    const start = Date.now();
    const res = http.get(`${BASE_URL}/transactions?page=1&page_size=20`, { headers });
    txnLatency.add(Date.now() - start);
    check(res, {
      "txn list 200": (r) => r.status === 200,
      "txn list has items": (r) => Array.isArray(r.json("items")),
    });
    errorRate.add(res.status !== 200);
  }

  sleep(1);
}
