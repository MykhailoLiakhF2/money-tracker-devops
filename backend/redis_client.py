"""
Redis client for Money Tracker.

Provides:
- Connection pool (reuse connections, don't create per request)
- Cache helpers (get/set with JSON serialization)
- Rate limiting (fixed window counter)
- Graceful degradation (app works if Redis is down, just without cache)

INTERVIEW NOTES:
  - Connection pooling is critical at scale: creating a new TCP connection
    per request adds ~1ms latency and exhausts file descriptors under load.
  - Graceful degradation: Redis is a cache, not source of truth.
    If Redis dies, we fall back to PostgreSQL. Users see slower responses,
    not errors. This is how high-availability systems handle Redis outages.
"""

import os
import json
import logging
from typing import Optional, Any

import redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection Pool (singleton)
# ---------------------------------------------------------------------------
# One pool shared across all requests. Default pool size: 10 connections.
# In production (high scale): pool size tuned per service, monitored via
# Prometheus metrics (redis_pool_active_connections, redis_pool_waiters).

_pool: Optional[redis.ConnectionPool] = None


def get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        _pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=0,
            decode_responses=True,      # Return strings, not bytes
            max_connections=20,
            socket_connect_timeout=2,   # Don't hang if Redis is unreachable
            socket_timeout=2,
        )
    return _pool


def get_redis() -> redis.Redis:
    """Get a Redis client from the connection pool."""
    return redis.Redis(connection_pool=get_pool())


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

def is_healthy() -> bool:
    """Check if Redis is reachable. Used in /ready endpoint."""
    try:
        return get_redis().ping()
    except redis.RedisError:
        return False


# ---------------------------------------------------------------------------
# Cache Helpers
# ---------------------------------------------------------------------------

def cache_get(key: str) -> Optional[Any]:
    """
    Get cached value by key. Returns None on miss or Redis error.

    Graceful degradation: if Redis is down, returns None → caller
    falls back to database. No exception propagated to user.
    """
    try:
        data = get_redis().get(key)
        if data is not None:
            return json.loads(data)
        return None
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.warning(f"Redis cache_get error for key={key}: {e}")
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 900) -> bool:
    """
    Set cached value with TTL. Default: 15 minutes.

    Returns True if cached successfully, False on error.
    TTL ensures stale data is automatically cleaned up.
    """
    try:
        serialized = json.dumps(value)
        get_redis().setex(key, ttl_seconds, serialized)
        return True
    except (redis.RedisError, TypeError) as e:
        logger.warning(f"Redis cache_set error for key={key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    """
    Delete a cached key. Used for cache invalidation.

    Example: when a new category is created, delete "categories:all"
    so the next GET reads fresh data from PostgreSQL.
    """
    try:
        get_redis().delete(key)
        return True
    except redis.RedisError as e:
        logger.warning(f"Redis cache_delete error for key={key}: {e}")
        return False


# ---------------------------------------------------------------------------
# Rate Limiting (Fixed Window Counter)
# ---------------------------------------------------------------------------
# How it works:
#   - Key: "ratelimit:{client_ip}"
#   - On each request: INCR key (atomic counter)
#   - First request sets EXPIRE to window_seconds
#   - If count > max_requests → reject with 429
#   - After window expires → key deleted → counter resets
#
# INTERVIEW NOTE:
#   Fixed window has edge case: 100 requests at 0:59 + 100 at 1:00
#   = 200 in 2 seconds. Sliding window (sorted sets) fixes this but
#   is more complex. Fixed window is standard for most APIs.
#   High-scale systems use sliding window for payment endpoints, fixed for reads.
# ---------------------------------------------------------------------------

def check_rate_limit(client_ip: str, max_requests: int = 100, window_seconds: int = 60) -> dict:
    """
    Check if client has exceeded rate limit.

    Returns:
        {"allowed": True/False, "current": count, "limit": max, "remaining": N}

    On Redis error: allows the request (fail-open).
    In fintech, some endpoints are fail-closed (deny on error) — depends on risk.
    """
    key = f"ratelimit:{client_ip}"
    try:
        r = get_redis()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        results = pipe.execute()

        current_count = results[0]
        current_ttl = results[1]

        # First request in window — set expiry
        if current_ttl == -1:
            r.expire(key, window_seconds)

        allowed = current_count <= max_requests
        remaining = max(0, max_requests - current_count)

        return {
            "allowed": allowed,
            "current": current_count,
            "limit": max_requests,
            "remaining": remaining,
        }
    except redis.RedisError as e:
        logger.warning(f"Redis rate_limit error for {client_ip}: {e}")
        # Fail-open: allow request if Redis is down
        return {"allowed": True, "current": 0, "limit": max_requests, "remaining": max_requests}
