"""Episodic memory — persists significant events across sessions."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    episode_id: str
    agent_id: str
    session_id: str
    event_type: str
    summary: str
    details: dict[str, Any]
    importance: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        agent_id: str,
        session_id: str,
        event_type: str,
        summary: str,
        details: dict[str, Any],
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> "Episode":
        return cls(
            episode_id=str(uuid.uuid4()),
            agent_id=agent_id,
            session_id=session_id,
            event_type=event_type,
            summary=summary,
            details=details,
            importance=importance,
            tags=tags or [],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d


class EpisodicMemory:
    """In-memory episodic store (replace with Postgres in production)."""

    def __init__(self, max_episodes: int = 1000) -> None:
        self._episodes: list[Episode] = []
        self._max_episodes = max_episodes

    def record(self, episode: Episode) -> None:
        self._episodes.append(episode)
        if len(self._episodes) > self._max_episodes:
            self._episodes = sorted(
                self._episodes, key=lambda e: e.importance, reverse=True
            )[: self._max_episodes]

    def recall(
        self,
        agent_id: str,
        event_type: str | None = None,
        min_importance: float = 0.0,
        limit: int = 20,
    ) -> list[Episode]:
        results = [
            e
            for e in self._episodes
            if e.agent_id == agent_id
            and e.importance >= min_importance
            and (event_type is None or e.event_type == event_type)
        ]
        return sorted(results, key=lambda e: e.created_at, reverse=True)[:limit]
