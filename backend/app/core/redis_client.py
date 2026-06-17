"""Async Redis client + helpers: JWT blacklist and a token-bucket rate limiter."""

from __future__ import annotations

import time

import redis.asyncio as redis

from app.core.config import settings

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Lazily create a singleton async Redis client."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


# --- JWT blacklist (logout / refresh rotation) ---

def _blacklist_key(jti: str) -> str:
    return f"jwt:blacklist:{jti}"


async def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    """Mark a token's jti revoked until it would have naturally expired."""
    if ttl_seconds <= 0:
        return
    await get_redis().set(_blacklist_key(jti), "1", ex=ttl_seconds)


async def is_blacklisted(jti: str) -> bool:
    return bool(await get_redis().exists(_blacklist_key(jti)))


# --- Token-bucket rate limiter ---
# Refill `capacity` tokens over `window_seconds`; each request costs 1 token.
# Implemented atomically in Lua so concurrent requests can't over-spend.

_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local refill_rate = capacity / window

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(window) * 2)
return allowed
"""


async def rate_limit_ok(identifier: str, capacity: int, window_seconds: int) -> bool:
    """Return True if a request from `identifier` is within budget."""
    allowed = await get_redis().eval(
        _BUCKET_LUA,
        1,
        f"ratelimit:{identifier}",
        capacity,
        window_seconds,
        time.time(),
    )
    return bool(allowed)
