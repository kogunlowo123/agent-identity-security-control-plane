"""agentctl — CLI entry point."""

from __future__ import annotations

import sys

import click

from . import __version__
from .scaffold import scaffold_agent
from .validate import validate_agents


@click.group()
@click.version_option(version=__version__, prog_name="agentctl")
@click.option("--api-url", default="http://localhost:8000", envvar="AICP_API_URL",
              help="AICP API URL")
@click.option("--token", default="", envvar="AICP_TOKEN",
              help="Bearer token for API authentication")
@click.pass_context
def main(ctx: click.Context, api_url: str, token: str) -> None:
    """agentctl — manage Agent Identity Security Control Plane agents."""
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url
    ctx.obj["token"] = token


@main.command()
@click.option("--spiffe-id", required=True, help="SPIFFE ID of the agent")
@click.option("--tier", required=True, type=click.Choice(["T0", "T1", "T2", "T3"]),
              help="Trust tier")
@click.option("--agent-id", required=True, help="Agent identifier")
@click.option("--ttl", default=None, type=int, help="Requested TTL in seconds")
@click.pass_context
def issue(ctx: click.Context, spiffe_id: str, tier: str, agent_id: str, ttl: int | None) -> None:
    """Issue a JWT token for an agent."""
    import httpx
    from rich.console import Console
    from rich.json import JSON

    console = Console()
    api_url = ctx.obj["api_url"]
    token = ctx.obj["token"]

    payload = {"spiffe_id": spiffe_id, "tier": tier, "agent_id": agent_id}
    if ttl:
        payload["requested_ttl"] = ttl

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{api_url}/api/v1/identities/issue", json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Error {exc.response.status_code}:[/red] {exc.response.text}")
        sys.exit(1)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error:[/red] {exc}")
        sys.exit(1)

    console.print(JSON(resp.text))


@main.command()
@click.argument("token_value")
@click.pass_context
def validate(ctx: click.Context, token_value: str) -> None:
    """Validate a JWT token."""
    import httpx
    from rich.console import Console
    from rich.json import JSON

    console = Console()
    api_url = ctx.obj["api_url"]

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{api_url}/api/v1/identities/validate",
                json={"token": token_value},
            )
            resp.raise_for_status()
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error:[/red] {exc}")
        sys.exit(1)

    data = resp.json()
    if data.get("valid"):
        console.print("[green]Token is valid[/green]")
    else:
        console.print(f"[red]Token is invalid:[/red] {data.get('error', 'unknown')}")
    console.print(JSON(resp.text))


@main.command()
@click.argument("identity_id")
@click.pass_context
def get(ctx: click.Context, identity_id: str) -> None:
    """Get an agent identity record."""
    import httpx
    from rich.console import Console
    from rich.json import JSON

    console = Console()
    api_url = ctx.obj["api_url"]
    token = ctx.obj["token"]
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{api_url}/api/v1/identities/{identity_id}", headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Error {exc.response.status_code}:[/red] {exc.response.text}")
        sys.exit(1)
    except httpx.RequestError as exc:
        console.print(f"[red]Connection error:[/red] {exc}")
        sys.exit(1)

    console.print(JSON(resp.text))


@main.command("scaffold")
@click.option("--name", required=True, help="Agent name (slug format)")
@click.option("--tier", required=True, type=click.Choice(["T0", "T1", "T2", "T3"]))
@click.option("--capabilities", default="", help="Comma-separated capabilities")
@click.option("--output-dir", default=".", help="Output directory for YAML file")
def scaffold_cmd(name: str, tier: str, capabilities: str, output_dir: str) -> None:
    """Scaffold a new agent YAML definition."""
    caps = [c.strip() for c in capabilities.split(",") if c.strip()]
    output_path = scaffold_agent(name=name, tier=tier, capabilities=caps, output_dir=output_dir)
    click.echo(f"Agent scaffolded: {output_path}")


@main.command("validate")
@click.option("--dir", "directory", default=".", help="Directory containing agent YAML files")
@click.option("--schema", default=None, help="Path to JSON schema file")
def validate_cmd(directory: str, schema: str | None) -> None:
    """Validate agent YAML files against the registry schema."""
    errors = validate_agents(directory=directory, schema_path=schema)
    if errors:
        for path, error in errors:
            click.echo(f"FAIL {path}: {error}", err=True)
        sys.exit(1)
    else:
        click.echo("All agent definitions are valid.")


if __name__ == "__main__":
    main()
