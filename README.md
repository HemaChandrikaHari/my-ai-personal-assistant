# My AI Personal Assistant

A modular assistant with a FastAPI backend, Next.js dashboard, Google Workspace and Todoist OAuth, Blueticks WhatsApp MCP integration, and a local ChatGPT-facing MCP bridge.

## Local development

1. Copy `.env.example` to `.env` and configure the provider OAuth credentials and token encryption key.
2. Start the backend and frontend using the existing local development instructions.
3. The ChatGPT-facing MCP server can run locally over stdio without an OpenAI API key. See [mcp-server/README.md](mcp-server/README.md).
4. The MCP bridge calls the existing backend's provider endpoints directly; ChatGPT provides the model and reasoning. It does not call the backend's `/api/v1/chat` endpoint.

## ChatGPT MCP bridge

The local bridge is in `mcp-server/server.py`. It exposes account listing, Gmail read, Google Calendar read/write, Todoist read/write, and scoped Blueticks WhatsApp tools. Backend OAuth scopes and explicit WhatsApp grants remain authoritative. Gmail is currently read-only because the configured Google OAuth grant uses `gmail.readonly`; Gmail sending is not exposed. For WhatsApp, discovery does not grant access: read/write/send scopes must be approved separately.

Configure the ChatGPT app to ask for confirmation before all write or send actions. Review the target, recipient and content before approving an action.

**ChatGPT plan limitation:** OpenAI's current documentation lists custom MCP connections with full read/write support for Business and Enterprise/Edu. Pro supports read/fetch access; Free does not currently have the documented custom MCP connection feature. See the [MCP setup guide](mcp-server/README.md) and verify current account/workspace permissions before attempting connection.

The existing dashboard's AI chat endpoint still uses `OPENAI_API_KEY`. It is not used by the ChatGPT MCP bridge. Do not call that endpoint if you want to avoid API usage.

## Identity and security

Local Compose deliberately enables a development-only `X-User-ID` identity. Production requires a validated per-user OIDC identity, TLS, short-lived user-scoped tokens, secrets management, rate limiting, backups, monitoring, and security review. Never expose the local development MCP server or its development identity on the public internet.

## Blueticks

The existing endpoint remains `https://api.blueticks.co/mcp`. Discovery is explicit and does not grant access. Tool invocation requires separately approved read, write or send scope. Unknown tools default to write permission. Credentials are read from runtime environment or encrypted OAuth storage; never commit secrets.

## AWS

The Terraform directory is a starter, not a completed deployment. It includes chargeable resources. No AWS infrastructure has been provisioned; review costs before any deployment.
