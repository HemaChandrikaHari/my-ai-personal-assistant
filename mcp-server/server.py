"""ChatGPT-facing MCP tools for the user's existing personal-assistant backend.

No model API is used here: ChatGPT supplies the reasoning; this server only
exposes narrowly-scoped actions implemented and authorized by the backend.
"""
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API = os.getenv("ASSISTANT_API_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("ASSISTANT_BACKEND_TOKEN", "")
APP_ENV = os.getenv("APP_ENV", "development").lower()
USER_ID = os.getenv("ASSISTANT_USER_ID", "local-developer")
TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
TIMEOUT = float(os.getenv("ASSISTANT_API_TIMEOUT", "30"))

mcp = FastMCP("My AI Personal Assistant", host="127.0.0.1",
              port=int(os.getenv("MCP_PORT", "8001")))


def headers() -> dict[str, str]:
    # X-User-ID is accepted only by the backend in development mode.
    if APP_ENV == "development":
        if not USER_ID:
            raise RuntimeError("ASSISTANT_USER_ID is required in development")
        return {"X-User-ID": USER_ID}
    if not TOKEN:
        raise RuntimeError("ASSISTANT_BACKEND_TOKEN is required outside development")
    return {"Authorization": "Bearer " + TOKEN}


async def api(method: str, path: str, *, params: dict | None = None,
              payload: dict | None = None) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.request(
            method, API + path, headers=headers(), params=params, json=payload
        )
        if response.is_error:
            # Keep provider credentials and raw authorization headers out of errors.
            try:
                detail = response.json().get("detail", "Backend request failed")
            except Exception:
                detail = "Backend request failed"
            raise RuntimeError(f"Assistant backend returned HTTP {response.status_code}: {detail}")
        if response.status_code == 204 or not response.content:
            return {"ok": True}
        return response.json()


@mcp.tool()
async def assistant_health() -> dict:
    """Check the health of the personal-assistant backend."""
    return await api("GET", "/health")


@mcp.tool()
async def list_connected_accounts() -> list:
    """Show which Google, Todoist and WhatsApp accounts are connected."""
    return await api("GET", "/api/v1/connections")


@mcp.tool()
async def list_integrations() -> list:
    """List connected integrations and their approved WhatsApp permissions."""
    return await api("GET", "/api/v1/integrations")


@mcp.tool()
async def gmail_list_messages(max_results: int = 10) -> dict:
    """List recent Gmail message IDs. Read-only; use gmail_get_message to read a selected message."""
    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20")
    return await api("GET", "/api/v1/google/gmail/messages",
                     params={"max_results": max_results})


@mcp.tool()
async def gmail_get_message(message_id: str) -> dict:
    """Read the headers and plain-text body of one Gmail message by ID."""
    if not message_id or len(message_id) > 256 or "/" in message_id:
        raise ValueError("Invalid Gmail message ID")
    return await api("GET", "/api/v1/google/gmail/messages/" + message_id)


@mcp.tool()
async def calendar_list_events(max_results: int = 20) -> dict:
    """List upcoming events in the primary Google Calendar. Read-only."""
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50")
    return await api("GET", "/api/v1/google/calendar/events",
                     params={"max_results": max_results})


@mcp.tool()
async def calendar_create_event(summary: str, start: str, end: str,
                                timezone: str = "Asia/Kolkata",
                                description: str = "") -> dict:
    """Create a Google Calendar event. This changes your calendar; confirm details with the user first."""
    if not summary.strip() or len(summary) > 500:
        raise ValueError("summary must contain 1-500 characters")
    if len(description) > 5000:
        raise ValueError("description must be at most 5000 characters")
    return await api("POST", "/api/v1/google/calendar/events", payload={
        "summary": summary, "start": start, "end": end,
        "timezone": timezone, "description": description or None,
    })


@mcp.tool()
async def todoist_list_tasks() -> Any:
    """List tasks from the connected Todoist account. Read-only."""
    return await api("GET", "/api/v1/todoist/tasks")


@mcp.tool()
async def todoist_create_task(content: str, description: str = "",
                              due_string: str = "", project_id: str = "") -> dict:
    """Create a Todoist task. This changes Todoist; confirm the task details with the user first."""
    if not content.strip() or len(content) > 500:
        raise ValueError("content must contain 1-500 characters")
    if len(description) > 5000 or len(due_string) > 100:
        raise ValueError("description or due_string is too long")
    payload = {"content": content}
    if description:
        payload["description"] = description
    if due_string:
        payload["due_string"] = due_string
    if project_id:
        payload["project_id"] = project_id
    return await api("POST", "/api/v1/todoist/tasks", payload=payload)


@mcp.tool()
async def list_whatsapp_tools() -> dict:
    """Discover available Blueticks WhatsApp tools and their input schemas. Discovery does not grant permission."""
    return await api("POST", "/api/v1/integrations/blueticks/discover", payload={})


@mcp.tool()
async def request_whatsapp_permission(scope: str) -> dict:
    """Request backend approval for WhatsApp read, write, or send scope. The owner must approve it in the assistant dashboard."""
    if scope not in {"read", "write", "send"}:
        raise ValueError("scope must be read, write, or send")
    return await api("POST", "/api/v1/approval-requests",
                     payload={"integration_id": "blueticks_whatsapp", "scope": scope})


@mcp.tool()
async def list_permission_requests() -> list:
    """List pending and completed WhatsApp permission requests."""
    return await api("GET", "/api/v1/approval-requests")


@mcp.tool()
async def call_whatsapp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict:
    """Call a discovered WhatsApp tool. Backend enforces separate approved read/write/send scopes; ask the user before sending or changing anything."""
    if not tool_name or len(tool_name) > 120 or "/" in tool_name:
        raise ValueError("Invalid WhatsApp tool name")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    return await api(
        "POST", "/api/v1/integrations/blueticks_whatsapp/tools/" + tool_name,
        payload={"arguments": arguments},
    )


if __name__ == "__main__":
    mcp.run(transport=TRANSPORT)
