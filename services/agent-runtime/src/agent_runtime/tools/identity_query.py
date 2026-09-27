"""Identity query tool for agent runtime."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_runtime.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class IdentityQueryTool(BaseTool):
    """Query agent identity records from the identity API."""

    name = "identity_query"
    description = "Query agent identity records, including tier, capabilities, and session data."
    required_capabilities = ["identity:read"]

    def __init__(self, api_url: str, api_token: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_token = api_token

    async def run(self, identity_id: str, **kwargs: Any) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._api_url}/api/v1/identities/{identity_id}",
                    headers={"Authorization": f"Bearer {self._api_token}"},
                )
                if resp.status_code == 404:
                    return ToolResult.fail(f"Identity {identity_id} not found")
                resp.raise_for_status()
                return ToolResult.ok(
                    data=resp.json(),
                    metadata={"identity_id": identity_id},
                )
        except httpx.HTTPStatusError as exc:
            logger.error("Identity query HTTP error: %s", exc)
            return ToolResult.fail(f"Identity query failed: {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("Identity query connection error: %s", exc)
            return ToolResult.fail(f"Identity query connection error: {exc}")
