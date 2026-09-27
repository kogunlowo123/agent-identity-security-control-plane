"""Idempotency key tracking to prevent duplicate session operations."""

from __future__ import annotations

import hashlib
import time
from typing import Any


class IdempotencyStore:
    """Tracks idempotency keys with TTL expiry."""

    def __init__(self, ttl: int = 86400) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def _purge(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    def check_and_set(self, key: str, result: Any) -> tuple[bool, Any]:
        """Check if key exists. If yes return (True, cached_result). If no, store and return (False, None)."""
        self._purge()
        if key in self._store:
            value, _ = self._store[key]
            return True, value
        self._store[key] = (result, time.time() + self._ttl)
        return False, None

    def make_key(self, namespace: str, **kwargs: Any) -> str:
        payload = f"{namespace}:" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return hashlib.sha256(payload.encode()).hexdigest()

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)
