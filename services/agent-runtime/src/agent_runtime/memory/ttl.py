"""TTL-based memory cache with automatic expiry."""

from __future__ import annotations

import time
from typing import Any, Iterator


class TTLCache:
    """Simple TTL cache for agent state items."""

    def __init__(self, default_ttl: int = 300) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expire_at = time.time() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (value, expire_at)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() > expire_at:
            del self._store[key]
            return None
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def purge_expired(self) -> int:
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        self.purge_expired()
        return len(self._store)

    def keys(self) -> Iterator[str]:
        self.purge_expired()
        yield from self._store.keys()
