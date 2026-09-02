"""Outbound ingest pacing. rps<=0 disables the limiter (tests / offline mocks)."""

from __future__ import annotations

import os
import threading
import time


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def ingest_rps() -> float:
    """Max provider HTTP calls per second. 0 = unlimited."""
    value = _env_float("STREET_INGEST_RPS", 2.0)
    if value < 0:
        raise ValueError("STREET_INGEST_RPS must be >= 0")
    return value


def ingest_concurrency() -> int:
    value = _env_int("STREET_INGEST_CONCURRENCY", 4)
    if value < 1:
        raise ValueError("STREET_INGEST_CONCURRENCY must be >= 1")
    return value


def ingest_max_symbols() -> int:
    """Hard cap. 0 = unlimited. Default 500 matches the Phase 2 acceptance target."""
    value = _env_int("STREET_INGEST_MAX_SYMBOLS", 500)
    if value < 0:
        raise ValueError("STREET_INGEST_MAX_SYMBOLS must be >= 0")
    return value


def ensure_ingest_symbol_count(count: int) -> None:
    cap = ingest_max_symbols()
    if cap and count > cap:
        raise ValueError(
            f"ingest supports at most {cap} symbols (got {count}); "
            "raise STREET_INGEST_MAX_SYMBOLS if you intend to pull a larger universe"
        )


class TokenBucket:
    """Thread-safe token bucket. ``rate<=0`` means acquire() is a no-op."""

    def __init__(self, rate: float, burst: float | None = None) -> None:
        self.rate = float(rate)
        self.burst = float(burst) if burst is not None else max(1.0, self.rate)
        self._tokens = self.burst
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        if self.rate <= 0 or tokens <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._updated
                self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
                self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self.rate
            time.sleep(wait)


_limiter: TokenBucket | None = None
_limiter_lock = threading.Lock()


def reset_ingest_limiter() -> None:
    """Drop the cached limiter so the next pace() re-reads env."""
    global _limiter
    with _limiter_lock:
        _limiter = None


def get_ingest_limiter() -> TokenBucket:
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            rate = ingest_rps()
            burst = _env_float("STREET_INGEST_BURST", max(1.0, rate if rate > 0 else 1.0))
            if burst < 1:
                raise ValueError("STREET_INGEST_BURST must be >= 1")
            _limiter = TokenBucket(rate=rate, burst=burst)
        return _limiter


def pace() -> None:
    """Block until the next outbound market-data HTTP call is allowed."""
    get_ingest_limiter().acquire()
