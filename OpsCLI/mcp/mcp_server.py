"""Six read-only OpsCLI operations exposed over real MCP stdio."""
import json
import subprocess
import sys
from mcp.server.fastmcp import FastMCP
from pathlib import Path
mcp = FastMCP("OpsCLI")



PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_cli(*args: str):
    command = [sys.executable, "-m", "opscli", *args]

    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            return {
                "error": "CLI execution failed",
                "exit_code": result.returncode,
                "details": result.stderr[:1000],
            }

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return {
            "error": "CLI subprocess timed out after 30 seconds",
            "command": list(args),
        }

    except Exception as exc:
        return {
            "error": str(exc),
            "command": list(args),
        }    

@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """Get ServiceNow incident details by ID, e.g. INC1001."""
    return run_cli("get-incident", incident_id)


@mcp.tool()
def list_incidents(status: str = "") -> list:
    """List incidents; optionally filter status (Open, In Progress, Resolved)."""
    args = ["list-incidents"]
    if status:
        if status not in ("Open", "In Progress", "Resolved"):
            return [{"error": "Invalid status"}]
        args.extend(["--status", status])
    return run_cli(*args)


@mcp.tool()
def search_incidents(query: str) -> list:
    """Search incidents by a keyword in ID, category, or description."""
    return run_cli("search-incidents", query)


@mcp.tool()
def search_defects(query: str) -> list:
    """Search mock Jira defects by error code or text, e.g. ACT-401."""
    return run_cli("search-defects", query)


@mcp.tool()
def incident_stats() -> dict:
    """Get incident counts grouped by status."""
    return run_cli("incident-stats")


@mcp.tool()
def health() -> dict:
    """Check whether the local OpsCLI service is healthy."""
    return run_cli("health")


if __name__ == "__main__":
    mcp.run(transport="stdio")
