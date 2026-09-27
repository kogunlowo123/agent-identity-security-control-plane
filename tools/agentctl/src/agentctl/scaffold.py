"""Agent YAML scaffolding from template."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


def scaffold_agent(
    name: str,
    tier: str,
    capabilities: list[str],
    output_dir: str = ".",
    trust_domain: str = "agent-identity-security-control-plane",
) -> str:
    """
    Generate a new agent YAML definition from a template.

    Args:
        name: Agent slug name (e.g. my-new-agent)
        tier: Trust tier (T0-T3)
        capabilities: List of capability strings
        output_dir: Directory to write the YAML file
        trust_domain: SPIFFE trust domain

    Returns:
        Path to the created YAML file
    """
    # Validate name is slug format
    if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", name):
        raise ValueError(
            f"Agent name '{name}' must be lowercase alphanumeric with hyphens (slug format)"
        )

    if tier not in {"T0", "T1", "T2", "T3"}:
        raise ValueError(f"tier must be T0, T1, T2, or T3, got: {tier}")

    max_depth = {"T0": 0, "T1": 2, "T2": 1, "T3": 0}[tier]
    spiffe_id = f"spiffe://{trust_domain}/{name}"
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    caps_yaml = "\n".join(f"  - {cap}" for cap in capabilities) if capabilities else "  []"

    content = f"""id: {name}
name: {name.replace("-", " ").title()}
description: >
  TODO: Describe the purpose and responsibilities of this agent.
spiffe_id: {spiffe_id}
tier: {tier}
status: pending
capabilities:
{caps_yaml}
authorized_tools: []
max_delegation_depth: {max_depth}
metadata:
  team: security-platform
  owner: kogunlowo123
  environment: production
created_at: "{now}"
updated_at: "{now}"
"""

    output_path = Path(output_dir) / f"{name}.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)
