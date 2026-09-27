"""Task planning for agent orchestration."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    name: str
    description: str
    agent_id: str
    priority: int
    payload: dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        agent_id: str,
        payload: dict[str, Any],
        priority: int = 5,
        depends_on: list[str] | None = None,
    ) -> "Task":
        return cls(
            task_id=str(uuid.uuid4()),
            name=name,
            description=description,
            agent_id=agent_id,
            priority=priority,
            payload=payload,
            depends_on=depends_on or [],
        )


@dataclass
class TaskPlan:
    plan_id: str
    session_id: str
    tasks: list[Task]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, session_id: str, tasks: list[Task]) -> "TaskPlan":
        return cls(
            plan_id=str(uuid.uuid4()),
            session_id=session_id,
            tasks=tasks,
        )

    def ready_tasks(self) -> list[Task]:
        """Return tasks whose dependencies are all completed."""
        completed_ids = {t.task_id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t
            for t in self.tasks
            if t.status == TaskStatus.PENDING and set(t.depends_on).issubset(completed_ids)
        ]

    def is_complete(self) -> bool:
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED) for t in self.tasks)

    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks)


class TaskPlanner:
    """Builds execution plans for identity audit workflows."""

    def plan_identity_audit(self, identity_id: str, session_id: str) -> TaskPlan:
        retrieve = Task.create(
            name="retrieve_context",
            description=f"Retrieve RAG context for identity {identity_id}",
            agent_id="identity-auditor",
            payload={"identity_id": identity_id, "query": f"identity audit {identity_id}"},
            priority=1,
        )
        analyze = Task.create(
            name="analyze_identity",
            description=f"Analyze identity record {identity_id}",
            agent_id="identity-auditor",
            payload={"identity_id": identity_id},
            priority=2,
            depends_on=[retrieve.task_id],
        )
        report = Task.create(
            name="generate_report",
            description=f"Generate audit report for {identity_id}",
            agent_id="identity-auditor",
            payload={"identity_id": identity_id},
            priority=3,
            depends_on=[analyze.task_id],
        )
        return TaskPlan.create(session_id=session_id, tasks=[retrieve, analyze, report])

    def plan_token_inspection(self, token_jti: str, session_id: str) -> TaskPlan:
        inspect = Task.create(
            name="inspect_token",
            description=f"Inspect token {token_jti}",
            agent_id="token-inspector",
            payload={"token_jti": token_jti},
            priority=1,
        )
        return TaskPlan.create(session_id=session_id, tasks=[inspect])
