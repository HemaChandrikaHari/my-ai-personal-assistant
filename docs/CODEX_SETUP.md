# Connect Codex to My AI Personal Assistant

The bridge supports MCP stdio transport for local Codex use. This is the recommended setup for development: the MCP process runs on your machine and calls your local FastAPI backend. Do not expose the unauthenticated HTTP bridge directly to the public internet.

## 1. Start the backend

From the repository root:

```bash
docker compose up --build postgres redis backend
```

Confirm `http://localhost:8000/health` responds with `{"status":"ok"}`.

## 2. Install the MCP bridge dependencies

Use the same Python environment in which you will run the MCP server:

```bash
python -m pip install -r mcp-server/requirements.txt
```

## 3. Configure Codex

Open `~/.codex/config.toml` (Windows: `%USERPROFILE%\.codex\config.toml`) and add:

```toml
[mcp_servers.my_ai_personal_assistant]
command = "python"
args = ["C:/absolute/path/to/my-ai-personal-assistant/mcp-server/server.py"]
env_vars = ["ASSISTANT_API_URL", "APP_ENV", "ASSISTANT_USER_ID"]
startup_timeout_sec = 20
tool_timeout_sec = 60

[mcp_servers.my_ai_personal_assistant.env]
ASSISTANT_API_URL = "http://localhost:8000"
APP_ENV = "development"
ASSISTANT_USER_ID = "local-developer"
```

Replace the example path with the absolute path to your local repository. If you use a virtual environment, set `command` to that environment's Python executable.

The development identity header is accepted only when the backend is running with `APP_ENV=development`. It is disabled in production. For production, use a user-scoped OIDC bearer token and set `ASSISTANT_BACKEND_TOKEN` in Codex's local environment instead of using `ASSISTANT_USER_ID`.

## 4. Restart and verify

Restart Codex, then run:

```bash
codex mcp list
```

In the Codex TUI, use `/mcp` to inspect the connected tools. Try `assistant_health`, `list_integrations`, `list_connected_accounts`, and `ask_assistant`.

## Available tools

- `assistant_health`: check backend health.
- `list_integrations`: see configured integrations and their granted scopes.
- `list_connected_accounts`: see Google and Todoist connection status.
- `ask_assistant`: chat with the assistant; it can use connected read-only Gmail, Calendar, Todoist and approved Blueticks read tools.

The MCP bridge does not expose direct write/send operations. Calendar event and Todoist task creation remain explicit dashboard actions. Do not share one backend token across multiple users.

## Optional private HTTP transport

Docker Compose can start the bridge at `http://localhost:8001/mcp`:

```bash
docker compose --profile mcp up --build mcp-server
```

This local Compose bridge uses the development identity by default. Do not publish port 8001 publicly without adding an authenticated reverse proxy or a proper MCP OAuth/authentication layer.
