# MCP bridge

The bridge exposes a small MCP surface for Codex and ChatGPT Desktop: backend health, integration status, connected account status, and assistant chat.

## Local Codex (recommended)

Use stdio transport and a local development identity. Follow [the Codex setup guide](../docs/CODEX_SETUP.md). The development identity works only while the backend has `APP_ENV=development`; production rejects `X-User-ID`.

## Optional local HTTP transport

Run with Docker Compose:

```bash
docker compose --profile mcp up --build mcp-server
```

This binds Streamable HTTP to localhost through Docker's port mapping. It uses the local development identity by default. Do not publish this unauthenticated HTTP bridge to the internet.

## Production

For production, configure a short-lived, user-scoped `ASSISTANT_BACKEND_TOKEN` issued by your OIDC identity provider, set `APP_ENV=production`, and put the MCP bridge behind an authenticated transport/reverse proxy. The backend remains the authorization source of truth. Do not share one privileged backend token across multiple users.
