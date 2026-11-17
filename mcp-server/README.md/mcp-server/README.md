# ChatGPT MCP interface
Deploy a separate MCP server that exposes curated assistant tools. Each tool must call the shared FastAPI backend and use the same identity and per-integration permission checks. Never expose raw credentials or bypass approval checks. Add OAuth/OIDC before public deployment.
