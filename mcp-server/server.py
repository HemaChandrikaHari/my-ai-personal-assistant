"""MCP bridge for local Codex/ChatGPT Desktop and optional private HTTP hosting."""
import os
import httpx
from mcp.server.fastmcp import FastMCP

API = os.getenv("ASSISTANT_API_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.getenv("ASSISTANT_BACKEND_TOKEN", "")
APP_ENV = os.getenv("APP_ENV", "development").lower()
USER_ID = os.getenv("ASSISTANT_USER_ID", "")
TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
mcp = FastMCP("My AI Personal Assistant")


def headers():
    # Local development can use the backend's dev-only identity header.
    # This path is rejected by the backend outside APP_ENV=development.
    if APP_ENV == "development" and USER_ID:
        return {"X-User-ID": USER_ID}
    if not TOKEN:
        raise RuntimeError("ASSISTANT_BACKEND_TOKEN is not configured")
    return {"Authorization": "Bearer " + TOKEN}


@mcp.tool()
async def assistant_health() -> dict:
    """Check whether the assistant backend is healthy."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(API + "/health")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_integrations() -> list:
    """List integrations visible to the identity mapped to this MCP connection."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(API + "/api/v1/integrations", headers=headers())
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_connected_accounts() -> list:
    """List Google and Todoist connections for the current backend identity."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(API + "/api/v1/connections", headers=headers())
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def ask_assistant(message: str) -> dict:
    """Ask the assistant. Chat can read only explicitly connected and approved sources; it does not perform writes."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            API + "/api/v1/chat", headers=headers(), json={"message": message}
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    mcp.run(transport=TRANSPORT)
