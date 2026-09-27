"""Validate agent YAML files against the JSON schema."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


def load_schema(schema_path: str | None = None) -> dict[str, Any]:
    """Load the agent identity JSON schema."""
    if schema_path:
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)

    # Default: look relative to this file
    default_path = Path(__file__).parent.parent.parent.parent.parent.parent / \
        "identity" / "registry" / "schema.json"
    if default_path.exists():
        with open(default_path, encoding="utf-8") as f:
            return json.load(f)

    # Fallback: minimal inline schema
    return {
        "type": "object",
        "required": ["id", "name", "tier", "status", "spiffe_id", "created_at"],
        "properties": {
            "tier": {"enum": ["T0", "T1", "T2", "T3"]},
            "status": {"enum": ["active", "suspended", "revoked", "pending"]},
            "spiffe_id": {"pattern": "^spiffe://"},
        },
    }


def validate_agent_yaml(
    yaml_path: str,
    schema: dict[str, Any],
) -> list[str]:
    """
    Validate a single agent YAML file against the schema.

    Returns:
        List of validation error messages (empty if valid)
    """
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed: pip install jsonschema"]

    errors = []

    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]

    if not isinstance(data, dict):
        return ["YAML content is not a mapping"]

    # JSON Schema validation
    validator = jsonschema.Draft7Validator(schema)
    for error in validator.iter_errors(data):
        errors.append(f"Schema: {error.message} (at {'.'.join(str(p) for p in error.path)})")

    # Additional semantic validation
    spiffe_id = data.get("spiffe_id", "")
    if spiffe_id and not re.match(r"^spiffe://[a-z0-9.-]+/[a-z0-9/._-]+$", spiffe_id):
        errors.append(f"Invalid SPIFFE ID format: {spiffe_id}")

    tier = data.get("tier", "")
    max_depth_config = {"T0": 0, "T1": 2, "T2": 1, "T3": 0}
    declared_depth = data.get("max_delegation_depth", 0)
    if tier in max_depth_config:
        tier_max = max_depth_config[tier]
        if declared_depth > tier_max:
            errors.append(
                f"max_delegation_depth {declared_depth} exceeds tier {tier} maximum {tier_max}"
            )

    return errors


def validate_agents(
    directory: str = ".",
    schema_path: str | None = None,
) -> list[tuple[str, str]]:
    """
    Validate all YAML files in a directory against the agent schema.

    Returns:
        List of (file_path, error_message) tuples for failed files
    """
    schema = load_schema(schema_path)
    failures: list[tuple[str, str]] = []

    yaml_files = list(Path(directory).glob("**/*.yaml")) + list(Path(directory).glob("**/*.yml"))

    if not yaml_files:
        print(f"No YAML files found in {directory}")
        return []

    for yaml_file in sorted(yaml_files):
        errors = validate_agent_yaml(str(yaml_file), schema)
        for error in errors:
            failures.append((str(yaml_file), error))

    return failures
