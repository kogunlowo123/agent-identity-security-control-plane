"""Budget enforcement for LLM gateway."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GatewayBudgetState:
    session_id: str
    tier: str
    token_limit: int
    cost_limit_usd: float
    tokens_used: int = 0
    cost_used_usd: float = 0.0
    request_count: int = 0
    last_request_at: float = field(default_factory=time.time)


class GatewayBudgetEnforcer:
    def __init__(self) -> None:
        self._states: dict[str, GatewayBudgetState] = {}

    def register(self, session_id: str, tier: str, token_limit: int, cost_limit_usd: float) -> None:
        self._states[session_id] = GatewayBudgetState(
            session_id=session_id,
            tier=tier,
            token_limit=token_limit,
            cost_limit_usd=cost_limit_usd,
        )

    def allow(self, session_id: str, requested_tokens: int) -> bool:
        state = self._states.get(session_id)
        if state is None:
            return True
        return (state.tokens_used + requested_tokens) <= state.token_limit

    def record(self, session_id: str, tokens: int, cost_usd: float) -> None:
        state = self._states.get(session_id)
        if state is None:
            return
        state.tokens_used += tokens
        state.cost_used_usd += cost_usd
        state.request_count += 1
        state.last_request_at = time.time()
        if state.tokens_used / state.token_limit > 0.9:
            logger.warning("Session %s at >90%% token budget", session_id)
