"""Short-term turn buffer for in-context conversation memory."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


@dataclass
class Turn:
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    token_count: int = 0


class TurnBuffer:
    """Fixed-capacity FIFO buffer for conversation turns."""

    def __init__(self, max_turns: int = 20, max_tokens: int = 4096) -> None:
        self._max_turns = max_turns
        self._max_tokens = max_tokens
        self._buffer: deque[Turn] = deque()
        self._total_tokens = 0

    def add(self, role: Literal["user", "assistant", "system"], content: str, token_count: int = 0) -> None:
        turn = Turn(role=role, content=content, token_count=token_count)
        self._buffer.append(turn)
        self._total_tokens += token_count
        self._evict()

    def _evict(self) -> None:
        while len(self._buffer) > self._max_turns:
            removed = self._buffer.popleft()
            self._total_tokens -= removed.token_count
        while self._total_tokens > self._max_tokens and self._buffer:
            removed = self._buffer.popleft()
            self._total_tokens -= removed.token_count

    def to_messages(self) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in self._buffer]

    def clear(self) -> None:
        self._buffer.clear()
        self._total_tokens = 0

    def __len__(self) -> int:
        return len(self._buffer)
