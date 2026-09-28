"""Holmes local MCP server: read-only lookups over synthetic JSON. No network, no actions."""

import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer

DATA = Path(__file__).parent / "data"
INDICATORS = json.loads((DATA / "indicators.json").read_text())
ASSETS = json.loads((DATA / "assets.json").read_text())
TECHNIQUES = json.loads((DATA / "techniques.json").read_text())

server = MCPServer("holmes-lookups")


@server.tool()
def lookup_indicator(indicator: str) -> dict:
    """Look up synthetic threat-intel reputation for a file hash, IP address, or domain."""
    record = INDICATORS.get(indicator.strip())
    return {"indicator": indicator, "found": True, **record} if record else {"indicator": indicator, "found": False}


@server.tool()
def get_asset_context(hostname: str) -> dict:
    """Get synthetic owner, business function, environment, and criticality for a hostname."""
    record = ASSETS.get(hostname.strip().upper())
    return {"hostname": hostname, "found": True, **record} if record else {"hostname": hostname, "found": False}


@server.tool()
def lookup_attack_technique(behavior: str) -> list[dict]:
    """Map an observed behavior description to MITRE ATT&CK-style techniques from a local catalog."""
    text = behavior.lower()
    return [
        {k: t[k] for k in ("id", "name", "tactic")}
        for t in TECHNIQUES
        if any(kw in text for kw in t["keywords"])
    ]


if __name__ == "__main__":
    server.run("stdio")
