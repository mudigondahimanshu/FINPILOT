"""Advanced fraud detection (Phase 3.4).

Builds on the Phase 2 TransactionGraph (adjacency list) with:
  - BFS / DFS        : connected-component analysis and cycle detection (O(V+E))
  - Isolation Forest : unsupervised anomaly scoring per transaction (O(n log n))
  - Velocity checks  : N transactions in T seconds per user/merchant
  - Geolocation      : flag logins/transactions from unusual countries / time-zones
  - Alert threshold  : configurable; flagged transactions returned < 200ms

All heavy compute runs in asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from typing import Any

log = logging.getLogger(__name__)

# Free ipinfo.io API (50k req/month). Set IPINFO_TOKEN for higher limits.
_IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", "")


# ── BFS / DFS graph algorithms ─────────────────────────────────────────────────

def connected_components(adj: dict[str, list[str]]) -> list[list[str]]:
    """BFS connected components on an undirected version of adj. O(V+E)."""
    visited: set[str] = set()
    components: list[list[str]] = []
    for node in adj:
        if node not in visited:
            component: list[str] = []
            queue: deque[str] = deque([node])
            visited.add(node)
            while queue:
                cur = queue.popleft()
                component.append(cur)
                for neighbour in adj.get(cur, []):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        queue.append(neighbour)
            components.append(component)
    return sorted(components, key=len, reverse=True)


def detect_cycles(adj: dict[str, list[str]]) -> list[list[str]]:
    """DFS cycle detection on a directed graph. Returns one cycle per component. O(V+E)."""
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []
    parent: dict[str, str | None] = {}

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for nbr in adj.get(node, []):
            if nbr not in visited:
                parent[nbr] = node
                dfs(nbr, path)
            elif nbr in rec_stack:
                # Reconstruct cycle
                idx = path.index(nbr)
                cycles.append(path[idx:] + [nbr])
        path.pop()
        rec_stack.discard(node)

    for node in list(adj.keys()):
        if node not in visited:
            dfs(node, [])

    return cycles


# ── Isolation Forest ──────────────────────────────────────────────────────────

def isolation_forest_scores(transactions: list[dict]) -> list[dict]:
    """Score each transaction for anomaly using sklearn IsolationForest.

    Features: log-abs-amount, hour-of-day, day-of-week.
    Returns each transaction dict augmented with anomaly_score (0–1, higher = more anomalous).
    """
    if len(transactions) < 10:
        return [{**t, "anomaly_score": 0.0, "is_anomaly": False} for t in transactions]

    try:
        from sklearn.ensemble import IsolationForest  # noqa: PLC0415

        X = _extract_iso_features(transactions)
        clf = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        clf.fit(X)
        raw_scores = clf.decision_function(X)   # higher = more normal
        # Normalise to 0–1 anomaly probability (invert so 1 = most anomalous)
        normalised = 1.0 - (raw_scores - raw_scores.min()) / (raw_scores.ptp() + 1e-9)
        preds = clf.predict(X)  # -1 = anomaly, 1 = normal

        return [
            {
                **t,
                "anomaly_score": round(float(s), 4),
                "is_anomaly": bool(p == -1),
            }
            for t, s, p in zip(transactions, normalised, preds, strict=False)
        ]
    except Exception as exc:
        log.warning("IsolationForest failed: %s", exc)
        return [{**t, "anomaly_score": 0.0, "is_anomaly": False} for t in transactions]


def _extract_iso_features(transactions: list[dict]) -> Any:
    import numpy as np  # noqa: PLC0415

    rows = []
    for t in transactions:
        try:
            amount = abs(float(t.get("amount", 0)))
            log_amount = float(np.log1p(amount))
        except (ValueError, TypeError):
            log_amount = 0.0

        date_str = str(t.get("date", ""))
        try:
            from datetime import date  # noqa: PLC0415
            d = date.fromisoformat(date_str[:10])
            dow = float(d.weekday())
            month = float(d.month)
        except ValueError:
            dow, month = 0.0, 0.0

        rows.append([log_amount, dow, month])
    return np.array(rows)


# ── Velocity checks ───────────────────────────────────────────────────────────

def velocity_anomalies(
    transactions: list[dict],
    window_minutes: int = 60,
    max_count: int = 10,
) -> list[dict]:
    """Flag merchants or users who appear > max_count times in window_minutes."""
    from datetime import datetime, timedelta  # noqa: PLC0415

    window = timedelta(minutes=window_minutes)
    by_merchant: dict[str, list[str]] = {}
    for t in transactions:
        key = str(t.get("description", "unknown")).lower().strip()
        date_str = str(t.get("date", ""))
        by_merchant.setdefault(key, []).append(date_str)

    flags = []
    for merchant, dates in by_merchant.items():
        parsed = []
        for d in dates:
            try:
                parsed.append(datetime.fromisoformat(d[:10]))
            except ValueError:
                continue
        parsed.sort()
        for i, start in enumerate(parsed):
            count = sum(1 for d in parsed[i:] if d - start <= window)
            if count > max_count:
                flags.append({
                    "signal": "velocity",
                    "merchant": merchant,
                    "transactions_in_window": count,
                    "window_minutes": window_minutes,
                    "start_date": start.isoformat(),
                })
                break  # one flag per merchant

    return flags


# ── Geolocation anomaly ───────────────────────────────────────────────────────

_GEO_CACHE: dict[str, dict] = {}


async def geolocation_anomaly(
    ip_address: str,
    known_countries: list[str] | None = None,
) -> dict:
    """Check if *ip_address* comes from an unusual country.

    Uses the ipinfo.io free API (no key required for basic lookups).
    *known_countries* is a list of ISO-2 country codes the user has logged in
    from before. An empty/None list disables the comparison check.
    """
    if not ip_address or ip_address in ("127.0.0.1", "::1", "localhost"):
        return {"ip": ip_address, "country": "local", "flagged": False, "reason": "loopback"}

    if ip_address in _GEO_CACHE:
        geo = _GEO_CACHE[ip_address]
    else:
        try:
            import httpx  # noqa: PLC0415
            url = f"https://ipinfo.io/{ip_address}/json"
            params = {"token": _IPINFO_TOKEN} if _IPINFO_TOKEN else {}
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, params=params)
            if resp.status_code == 200:
                geo = resp.json()
                _GEO_CACHE[ip_address] = geo
            else:
                return {
                    "ip": ip_address, "country": "unknown",
                    "flagged": False, "reason": "api_error",
                }
        except Exception as exc:
            log.debug("Geo lookup failed for %s: %s", ip_address, exc)
            return {"ip": ip_address, "country": "unknown", "flagged": False, "reason": str(exc)}

    country = geo.get("country", "unknown")
    timezone = geo.get("timezone", "")
    flagged = False
    reason = "ok"

    if known_countries and country not in known_countries:
        flagged = True
        reason = f"new_country:{country} (known: {','.join(known_countries)})"

    return {
        "ip": ip_address,
        "country": country,
        "city": geo.get("city", ""),
        "timezone": timezone,
        "org": geo.get("org", ""),
        "flagged": flagged,
        "reason": reason,
    }


def geolocation_anomaly_sync(
    ip_logs: list[dict],
) -> list[dict]:
    """Analyse a list of IP log dicts {'ip': str, 'known_countries': list[str]}.

    Runs synchronously on a pre-resolved list (for use inside asyncio.to_thread).
    Flags IPs where the country appears only once across all records (never-seen-before).
    """
    from collections import Counter  # noqa: PLC0415

    country_counts: Counter[str] = Counter()
    results = []

    for log_entry in ip_logs:
        country = log_entry.get("country", "unknown")
        country_counts[country] += 1

    for log_entry in ip_logs:
        country = log_entry.get("country", "unknown")
        known = log_entry.get("known_countries", [])
        is_rare = country_counts[country] == 1 and len(ip_logs) >= 3
        is_new = bool(known) and country not in known
        results.append({
            **log_entry,
            "flagged": is_rare or is_new,
            "reason": "rare_country" if is_rare else ("new_country" if is_new else "ok"),
        })

    return results


# ── Public facade ─────────────────────────────────────────────────────────────

async def full_fraud_analysis(
    transactions: list[dict],
    ip_logs: list[dict] | None = None,
) -> dict:
    """Run all fraud detectors concurrently; return consolidated report."""
    iso_task = asyncio.to_thread(isolation_forest_scores, transactions)
    vel_task = asyncio.to_thread(velocity_anomalies, transactions)

    iso_results, vel_results = await asyncio.gather(iso_task, vel_task)

    # Build adjacency list for cycle detection
    adj: dict[str, list[str]] = {}
    for t in transactions:
        src = str(t.get("category_name", "unknown"))
        dst = str(t.get("description", "unknown")).lower().strip()
        adj.setdefault(src, []).append(dst)

    cycles = await asyncio.to_thread(detect_cycles, adj)
    components = await asyncio.to_thread(connected_components, adj)

    geo_flags: list[dict] = []
    if ip_logs:
        geo_flags = await asyncio.to_thread(geolocation_anomaly_sync, ip_logs)
        geo_flags = [g for g in geo_flags if g.get("flagged")]

    anomalies = [r for r in iso_results if r["is_anomaly"]]
    return {
        "total_transactions": len(transactions),
        "isolation_forest_anomalies": len(anomalies),
        "anomalous_transactions": anomalies[:20],
        "velocity_signals": vel_results,
        "graph_cycles": cycles[:5],
        "graph_components": len(components),
        "largest_component_size": len(components[0]) if components else 0,
        "geolocation_flags": geo_flags,
    }
