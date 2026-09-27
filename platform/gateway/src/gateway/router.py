"""LLM request router using LiteLLM."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

TIER_BUDGET_TOKENS = {"T0": 200_000, "T1": 100_000, "T2": 50_000, "T3": 10_000}

TIER_MODELS = {
    "T0": ["vertex_ai/gemini-1.5-pro", "gpt-4o"],
    "T1": ["vertex_ai/gemini-1.5-pro", "vertex_ai/gemini-1.5-flash", "gpt-4o-mini"],
    "T2": ["vertex_ai/gemini-1.5-flash", "gpt-4o-mini"],
    "T3": ["vertex_ai/gemini-1.5-flash"],
}


class GatewayRouter:
    """Routes LLM requests based on agent tier with budget enforcement."""

    def __init__(self) -> None:
        self._session_usage: dict[str, int] = {}

    def _check_budget(self, session_id: str, tier: str, requested_tokens: int) -> bool:
        used = self._session_usage.get(session_id, 0)
        budget = TIER_BUDGET_TOKENS.get(tier, 10_000)
        return (used + requested_tokens) <= budget

    def _record_usage(self, session_id: str, tokens_used: int) -> None:
        self._session_usage[session_id] = self._session_usage.get(session_id, 0) + tokens_used

    async def complete(
        self,
        messages: list[dict],
        session_id: str,
        tier: str,
        model: str | None = None,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> dict:
        try:
            import litellm
        except ImportError as exc:
            raise ImportError("litellm required: pip install litellm") from exc

        if not self._check_budget(session_id, tier, max_tokens):
            raise ValueError(f"Token budget exceeded for session {session_id} tier {tier}")

        models = TIER_MODELS.get(tier, TIER_MODELS["T3"])
        selected_model = model if model in models else models[0]

        start = time.time()
        try:
            response = await litellm.acompletion(
                model=selected_model,
                messages=messages,
                max_tokens=max_tokens,
                **kwargs,
            )
            tokens_used = response.usage.total_tokens if response.usage else max_tokens
            self._record_usage(session_id, tokens_used)
            elapsed = time.time() - start
            logger.info(
                "LLM request completed: session=%s tier=%s model=%s tokens=%d elapsed=%.2fs",
                session_id,
                tier,
                selected_model,
                tokens_used,
                elapsed,
            )
            return {"response": response, "model": selected_model, "tokens": tokens_used}
        except Exception as exc:
            logger.error("LLM request failed on %s: %s", selected_model, exc)
            for fallback in models[1:]:
                if fallback == selected_model:
                    continue
                try:
                    response = await litellm.acompletion(
                        model=fallback,
                        messages=messages,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                    tokens_used = response.usage.total_tokens if response.usage else max_tokens
                    self._record_usage(session_id, tokens_used)
                    logger.info("Fallback succeeded: model=%s", fallback)
                    return {"response": response, "model": fallback, "tokens": tokens_used}
                except Exception as exc2:
                    logger.error("Fallback %s also failed: %s", fallback, exc2)
            raise RuntimeError(f"All LLM providers failed for tier {tier}") from exc
