# ChatGPT MCP bridge

Run with ASSISTANT_API_URL and a short-lived, user-scoped ASSISTANT_BACKEND_TOKEN supplied at runtime, then run python server.py.

This bridge exposes health, integration listing and assistant chat only. It does not expose arbitrary Blueticks tool invocation. The bearer token must represent one backend user; do not share one privileged token across ChatGPT users. For multi-user deployment, implement OAuth/OIDC identity mapping and per-user token exchange before publishing the MCP endpoint. The backend remains the authorization source of truth.
