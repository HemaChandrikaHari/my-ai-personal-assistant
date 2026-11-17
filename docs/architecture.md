# Architecture

FastAPI is the authorization and data source of truth. The Next.js dashboard and restricted ChatGPT MCP bridge call the same API. PostgreSQL stores integrations, discovered capabilities, approval requests, per-user scope grants and audit events. Redis is reserved for asynchronous work.

## Authorization lifecycle
1. Discover integration capabilities (discovery alone does not enable actions).
2. User requests a specific integration scope.
3. User approves or rejects that request.
4. Backend persists a grant for that user, integration and scope.
5. Every tool invocation checks the grant server-side.

Read, write and send are independent. Unknown Blueticks tools default to write. Populate exact read-only and send tool names from trusted inspection of the server's capabilities.

## Trust boundaries
Incoming WhatsApp messages, email, documents and MCP results are untrusted data. They cannot modify policy, grant access or authorize actions. The ChatGPT bridge exposes health, integration listing and assistant chat only; it does not expose arbitrary integration execution.

## Components
- backend/app: FastAPI API, JWT auth, SQLAlchemy models, MCP adapter, OpenAI chat.
- frontend: Next.js dashboard for chat, discovery and scope approvals.
- mcp-server: restricted ChatGPT-facing MCP bridge.
- backend/app/worker.py: minimal Redis queue skeleton.
- infrastructure/aws/terraform: AWS infrastructure starter; deployment services still need completion and validation.
