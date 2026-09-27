"""Human-in-the-loop approval handling for high-risk agent actions."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

APPROVAL_TIMEOUT_SECONDS = 300


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


@dataclass
class ApprovalRequest:
    approval_id: str
    session_id: str
    agent_id: str
    action: str
    rationale: str
    payload: dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(seconds=APPROVAL_TIMEOUT_SECONDS)
    )
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    review_note: str | None = None

    @classmethod
    def create(
        cls,
        session_id: str,
        agent_id: str,
        action: str,
        rationale: str,
        payload: dict[str, Any],
    ) -> "ApprovalRequest":
        return cls(
            approval_id=str(uuid.uuid4()),
            session_id=session_id,
            agent_id=agent_id,
            action=action,
            rationale=rationale,
            payload=payload,
        )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def approve(self, reviewer: str, note: str = "") -> None:
        if self.is_expired:
            self.status = ApprovalStatus.TIMED_OUT
            return
        self.status = ApprovalStatus.APPROVED
        self.reviewed_at = datetime.now(timezone.utc)
        self.reviewer = reviewer
        self.review_note = note

    def reject(self, reviewer: str, note: str = "") -> None:
        self.status = ApprovalStatus.REJECTED
        self.reviewed_at = datetime.now(timezone.utc)
        self.reviewer = reviewer
        self.review_note = note


HIGH_RISK_ACTIONS = {
    "token:revoke",
    "identity:delete",
    "delegation:chain:break",
    "registry:entry:delete",
}


class ApprovalGate:
    """Gate that requires human approval for high-risk agent actions."""

    def __init__(self) -> None:
        self._pending: dict[str, ApprovalRequest] = {}

    def requires_approval(self, action: str) -> bool:
        return action in HIGH_RISK_ACTIONS

    def request_approval(
        self,
        session_id: str,
        agent_id: str,
        action: str,
        rationale: str,
        payload: dict[str, Any],
    ) -> ApprovalRequest:
        req = ApprovalRequest.create(
            session_id=session_id,
            agent_id=agent_id,
            action=action,
            rationale=rationale,
            payload=payload,
        )
        self._pending[req.approval_id] = req
        logger.info(
            "Approval requested: %s action=%s agent=%s",
            req.approval_id,
            action,
            agent_id,
        )
        return req

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        return self._pending.get(approval_id)

    def list_pending(self) -> list[ApprovalRequest]:
        now = datetime.now(timezone.utc)
        result = []
        for req in self._pending.values():
            if req.status == ApprovalStatus.PENDING:
                if req.expires_at <= now:
                    req.status = ApprovalStatus.TIMED_OUT
                else:
                    result.append(req)
        return result
