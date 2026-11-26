# My AI Personal Assistant

A modular assistant with a FastAPI API, Next.js dashboard, a restricted ChatGPT MCP bridge, per-user integration approvals, and an AWS infrastructure starter.

## Local development
1. Install Docker Desktop with Docker Compose.
2. Copy .env.example to .env.
3. Set OPENAI_API_KEY only if you want model chat. Leave BLUETICKS_BEARER_TOKEN empty unless the Blueticks MCP endpoint explicitly requires a bearer token. Never commit .env.
4. Run docker compose up --build.
5. Open http://localhost:3000 and check http://localhost:8000/health.

Local Compose deliberately enables a development-only X-User-ID identity. Production requires an HS256 JWT containing sub and exp claims and a JWT_SECRET of at least 32 characters. Replace this bootstrap with a real OIDC identity provider before internet exposure. Set NEXT_PUBLIC_ENABLE_DEV_AUTH=false in production.

## Database migrations
Development startup creates tables for convenience. For production, run Alembic migrations from the backend directory:
- py -m alembic upgrade head
- py -m alembic current

## Blueticks
The existing endpoint remains https://api.blueticks.co/mcp. Discovery is explicit and does not grant access. Tool invocation requires a separately approved read, write or send scope. Set BLUETICKS_READ_ONLY_TOOLS and BLUETICKS_SEND_TOOLS to exact tool names after inspecting capabilities; do not guess tool names. The AI chat tool loop exposes only discovered tools on the read-only allowlist and only after that user has approved the read scope. It never automatically invokes write or send tools. Direct tool invocation still requires the corresponding per-user scope. Unknown tools default to write permission. Credentials are read from runtime environment only; use AWS Secrets Manager in deployment. Existing Blueticks credentials are not stored in this repository or copied from ChatGPT's separate connection.

## Assistant chat
The chat endpoint supports a bounded OpenAI function-calling loop for explicitly allowlisted, discovered Blueticks read-only tools. Users must first discover capabilities, configure exact tool names in BLUETICKS_READ_ONLY_TOOLS, and approve the read scope. The model cannot automatically invoke write/send tools. Tool results are treated as untrusted input and truncated before being returned to the model.

## Google and Todoist OAuth

The API includes per-user OAuth connection flows for Google and Todoist. Configure the provider client IDs/secrets and exact callback URLs in `.env`, and generate a Fernet encryption key for `TOKEN_ENCRYPTION_KEY` (for example, with Python's `Fernet.generate_key()`). Keep the encryption key stable and back it up securely: losing it makes stored tokens unreadable. Never commit the resulting values.

Register these exact local callback URLs in each provider console:
- Google: `http://localhost:8000/api/v1/oauth/google/callback`
- Todoist: `http://localhost:8000/api/v1/oauth/todoist/callback`

Google OAuth requests Gmail read-only and Calendar event access. Todoist requests `data:read_write`; users can choose read-only access if offered by Todoist, in which case task creation is rejected by the API. The backend encrypts access/refresh tokens at rest, stores hashed one-time OAuth state for ten minutes, refreshes expiring tokens, and supports disconnecting local credentials. Provider credentials must be configured by the owner; the code cannot register OAuth apps or accept consent on their behalf.

API routes: `GET /api/v1/connections`, `GET /api/v1/oauth/{google|todoist}/start`, `GET /api/v1/google/gmail/messages`, `GET /api/v1/google/calendar/events`, `POST /api/v1/google/calendar/events`, `GET /api/v1/todoist/tasks`, `POST /api/v1/todoist/tasks`, and `DELETE /api/v1/connections/{google|todoist}`. Write endpoints perform the specific requested operation directly; keep them behind an explicit user action/confirmation in any AI workflow.

## ChatGPT MCP
The restricted bridge is in mcp-server/server.py. Run it with docker compose --profile mcp up --build mcp-server after supplying a short-lived, user-scoped ASSISTANT_BACKEND_TOKEN. The bridge exposes health, integration listing and assistant chat only. Do not share one backend token among multiple users.

## AWS
The Terraform directory is a starter for VPC, ECR, ECS cluster, encrypted RDS with AWS-managed credentials, Redis, IAM roles, CloudWatch and ALB. It is not a complete deployable environment: ECS task definitions/services, WAF, ACM, autoscaling, application secret injection and operational alarms still need implementation and review. Review monthly costs before provisioning.

## Current limitations
- Real OIDC, issuer/audience validation, token refresh/revocation and multi-user identity mapping are not yet implemented.
- The Redis worker is a safe queue skeleton; concrete task handlers, retries with backoff and scheduler are not yet implemented.
- Live Blueticks discovery/tool execution requires the runtime credentials and exact tool-scope allowlists configured by the owner.
- AWS infrastructure has not been applied. Docker and Terraform CLIs were not available in the current development environment.
- Configure TLS, WAF, rate limits, backups, restore tests, monitoring, secrets injection and security scans before production use.
