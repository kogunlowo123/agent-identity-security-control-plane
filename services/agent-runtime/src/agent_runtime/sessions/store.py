"""Session state store."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SessionRecord:
    session_id: str
    agent_id: str
    identity_id: str
    tier: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, agent_id: str, identity_id: str, tier: str, metadata: dict | None = None) -> "SessionRecord":
        return cls(
            session_id=str(uuid.uuid4()),
            agent_id=agent_id,
            identity_id=identity_id,
            tier=tier,
            status="active",
            metadata=metadata or {},
        )

    def close(self) -> None:
        self.status = "closed"
        self.updated_at = datetime.now(timezone.utc)


class SessionStore:
    """In-memory session store (replace with Postgres in production)."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, agent_id: str, identity_id: str, tier: str, metadata: dict | None = None) -> SessionRecord:
        session = SessionRecord.create(agent_id=agent_id, identity_id=identity_id, tier=tier, metadata=metadata)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def close(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.close()
        return True

    def list_active(self, agent_id: str | None = None) -> list[SessionRecord]:
        return [
            s for s in self._sessions.values()
            if s.status == "active" and (agent_id is None or s.agent_id == agent_id)
        ]
