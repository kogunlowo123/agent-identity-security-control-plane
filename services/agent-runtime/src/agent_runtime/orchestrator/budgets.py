"""Token and cost budget enforcement for agent sessions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

TIER_TOKEN_BUDGETS: dict[str, int] = {
    "T0": 200_000,
    "T1": 100_000,
    "T2": 50_000,
    "T3": 10_000,
}

TIER_COST_BUDGETS_USD: dict[str, float] = {
    "T0": 10.0,
    "T1": 5.0,
    "T2": 2.0,
    "T3": 0.5,
}


@dataclass
class BudgetState:
    session_id: str
    tier: str
    token_budget: int
    cost_budget_usd: float
    tokens_used: int = 0
    cost_used_usd: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    @classmethod
    def for_session(cls, session_id: str, tier: str) -> "BudgetState":
        return cls(
            session_id=session_id,
            tier=tier,
            token_budget=TIER_TOKEN_BUDGETS.get(tier, TIER_TOKEN_BUDGETS["T3"]),
            cost_budget_usd=TIER_COST_BUDGETS_USD.get(tier, TIER_COST_BUDGETS_USD["T3"]),
        )

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.token_budget - self.tokens_used)

    @property
    def cost_remaining_usd(self) -> float:
        return max(0.0, self.cost_budget_usd - self.cost_used_usd)

    @property
    def token_utilization(self) -> float:
        if self.token_budget == 0:
            return 1.0
        return self.tokens_used / self.token_budget

    def record_usage(self, tokens: int, cost_usd: float) -> None:
        self.tokens_used += tokens
        self.cost_used_usd += cost_usd
        self.last_updated = time.time()


class BudgetEnforcer:
    """Tracks and enforces per-session token and cost budgets."""

    def __init__(self) -> None:
        self._budgets: dict[str, BudgetState] = {}

    def get_or_create(self, session_id: str, tier: str) -> BudgetState:
        if session_id not in self._budgets:
            self._budgets[session_id] = BudgetState.for_session(session_id, tier)
        return self._budgets[session_id]

    def check_budget(
        self, session_id: str, tier: str, requested_tokens: int
    ) -> tuple[Literal["ok", "exceeded"], str]:
        budget = self.get_or_create(session_id, tier)
        if budget.tokens_remaining < requested_tokens:
            msg = (
                f"Token budget exceeded for session {session_id}: "
                f"requested {requested_tokens}, remaining {budget.tokens_remaining}"
            )
            logger.warning(msg)
            return "exceeded", msg
        return "ok", ""

    def record_usage(self, session_id: str, tier: str, tokens: int, cost_usd: float) -> None:
        budget = self.get_or_create(session_id, tier)
        budget.record_usage(tokens, cost_usd)
        if budget.token_utilization > 0.8:
            logger.warning(
                "Session %s at %.0f%% token budget utilization",
                session_id,
                budget.token_utilization * 100,
            )

    def summary(self, session_id: str) -> dict | None:
        budget = self._budgets.get(session_id)
        if not budget:
            return None
        return {
            "session_id": budget.session_id,
            "tier": budget.tier,
            "token_budget": budget.token_budget,
            "tokens_used": budget.tokens_used,
            "tokens_remaining": budget.tokens_remaining,
            "cost_budget_usd": budget.cost_budget_usd,
            "cost_used_usd": budget.cost_used_usd,
            "token_utilization": budget.token_utilization,
        }
