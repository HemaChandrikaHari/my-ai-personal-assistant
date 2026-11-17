"""ChatGPT-facing MCP bridge. Configure a user-scoped backend JWT at runtime."""
import os
import httpx
from mcp.server.fastmcp import FastMCP

API = os.getenv("ASSISTANT_API_URL", "http://localhost:8000")
TOKEN = os.getenv("ASSISTANT_BACKEND_TOKEN", "")
mcp = FastMCP("My AI Personal Assistant", host="0.0.0.0", port=8001)

def headers():
    if not TOKEN:
        raise RuntimeError("ASSISTANT_BACKEND_TOKEN is not configured")
    return {"Authorization": "Bearer " + TOKEN}

@mcp.tool()
async def assistant_health() -> dict:
    """Check whether the shared assistant backend is healthy."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(API + "/health")
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def list_integrations() -> list:
    """List integrations visible to the identity mapped to this backend token."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(API + "/api/v1/integrations", headers=headers())
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def ask_assistant(message: str) -> dict:
    """Ask the assistant. This tool does not perform external actions."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(API + "/api/v1/chat", headers=headers(), json={"message": message})
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
