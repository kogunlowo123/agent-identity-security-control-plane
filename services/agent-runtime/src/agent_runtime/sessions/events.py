"""Session event emission using CloudEvents spec."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

CLOUD_EVENTS_VERSION = "1.0"


@dataclass
class SessionEvent:
    specversion: str = CLOUD_EVENTS_VERSION
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "urn:aicp:agent-runtime"
    type: str = ""
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict[str, Any] = field(default_factory=dict)
    datacontenttype: str = "application/json"

    def to_json(self) -> str:
        return json.dumps(
            {
                "specversion": self.specversion,
                "id": self.id,
                "source": self.source,
                "type": self.type,
                "time": self.time,
                "datacontenttype": self.datacontenttype,
                "data": self.data,
            }
        )


def session_started_event(session_id: str, agent_id: str, tier: str) -> SessionEvent:
    return SessionEvent(
        type="com.aicp.session.started",
        data={"session_id": session_id, "agent_id": agent_id, "tier": tier},
    )


def session_closed_event(session_id: str, agent_id: str, reason: str = "normal") -> SessionEvent:
    return SessionEvent(
        type="com.aicp.session.closed",
        data={"session_id": session_id, "agent_id": agent_id, "reason": reason},
    )


def budget_exceeded_event(session_id: str, agent_id: str, tokens_used: int) -> SessionEvent:
    return SessionEvent(
        type="com.aicp.session.budget_exceeded",
        data={"session_id": session_id, "agent_id": agent_id, "tokens_used": tokens_used},
    )
