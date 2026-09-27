"""Audit logging for LLM gateway requests."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def _scrub_pii(text: str) -> str:
    return EMAIL_RE.sub("[REDACTED_EMAIL]", text)


@dataclass
class GatewayAuditRecord:
    request_id: str
    session_id: str
    agent_id: str
    tier: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class GatewayAuditLogger:
    def __init__(self) -> None:
        self._records: list[GatewayAuditRecord] = []

    def log(
        self,
        session_id: str,
        agent_id: str,
        tier: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        latency_ms: float,
        status: str = "success",
    ) -> GatewayAuditRecord:
        record = GatewayAuditRecord(
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            agent_id=agent_id,
            tier=tier,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
        )
        self._records.append(record)
        logger.info("GATEWAY_AUDIT %s", record.to_json())
        return record
