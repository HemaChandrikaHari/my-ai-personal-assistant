# My AI Personal Assistant

A modular assistant with a FastAPI API, Next.js dashboard, a restricted ChatGPT MCP bridge, per-user integration approvals, and an AWS infrastructure starter.

## Local development
1. Install Docker Desktop with Docker Compose.
2. Copy .env.example to .env.
3. Set OPENAI_API_KEY only if you want model chat. Leave BLUETICKS_BEARER_TOKEN empty unless the Blueticks MCP endpoint explicitly requires a bearer token. Never commit .env.
4. Run docker compose up --build.
5. Open http://localhost:3000 and check http://localhost:8000/health.

Local Compose deliberately enables a development-only X-User-ID identity. Production requires an external OIDC provider and RS256 bearer tokens validated against OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL. Configure these values before starting with APP_ENV=production; production startup fails closed if they are missing. Set NEXT_PUBLIC_ENABLE_DEV_AUTH=false in production. The API validates externally issued access tokens; it does not implement an interactive identity-provider login screen.

## Database migrations
Development startup creates tables for convenience. For production, run Alembic migrations from the backend directory:
- py -m alembic upgrade head
- py -m alembic current

## Blueticks

The existing endpoint remains https://api.blueticks.co/mcp. Connect Blueticks from the dashboard using OAuth 2.0 authorization code + S256 PKCE and dynamic client registration. The backend encrypts access/refresh tokens at rest and refreshes expired access tokens. The local callback is http://localhost:8000/api/v1/oauth/blueticks/callback (configured by BLUETICKS_REDIRECT_URI); production must set an HTTPS callback. Blueticks dynamic client registration is automatic, so no separate OAuth app registration is needed. The WhatsApp number must already be linked to the user's Blueticks account.

OAuth consent is separate from this app's internal tool permissions. Discovery is explicit and does not grant access. Tool invocation requires a separately approved per-user read, write or send scope. Set BLUETICKS_READ_ONLY_TOOLS and BLUETICKS_SEND_TOOLS to exact tool names only after inspecting capabilities; do not guess tool names. The AI chat tool loop exposes only discovered tools on the read-only allowlist after the user approves read access. It never automatically invokes write or send tools. Unknown tools default to write permission. Existing credentials from ChatGPT's separate Blueticks connection are not copied into this project.

## Assistant chat
The chat endpoint supports a bounded OpenAI function-calling loop for explicitly allowlisted, discovered Blueticks read-only tools and connected Google/Todoist read tools. Blueticks users must first discover capabilities, configure exact tool names in BLUETICKS_READ_ONLY_TOOLS, and approve the read scope. Google/Todoist read tools are offered only when the user has connected the account and the provider granted the corresponding read scope. The model cannot automatically invoke write/send tools. Tool results are treated as untrusted input and truncated before being returned to the model.

## Google, Todoist and Blueticks OAuth

The API includes per-user OAuth connection flows for Google, Todoist and Blueticks. Configure the provider client IDs/secrets and exact callback URLs in `.env`, and generate a Fernet encryption key for `TOKEN_ENCRYPTION_KEY` (for example, with Python's `Fernet.generate_key()`). Keep the encryption key stable and back it up securely: losing it makes stored tokens unreadable. Never commit the resulting values.

Register these exact local callback URLs in each provider console (Blueticks uses dynamic client registration automatically):
- Google: `http://localhost:8000/api/v1/oauth/google/callback`
- Todoist: `http://localhost:8000/api/v1/oauth/todoist/callback`

Google OAuth requests Gmail read-only and Calendar event access. Todoist requests `data:read_write`; users can choose read-only access if offered by Todoist, in which case task creation is rejected by the API. The backend encrypts access/refresh tokens at rest, stores hashed one-time OAuth state for ten minutes, refreshes expiring tokens, and supports disconnecting local credentials. Google and Todoist OAuth app credentials must be configured by the owner. Blueticks uses dynamic client registration, but the owner must still sign in and approve the OAuth consent screen.

API routes: `GET /api/v1/connections`, `POST /api/v1/jobs/refresh-connection`, `GET /api/v1/oauth/{google|todoist|blueticks}/start`, `GET /api/v1/google/gmail/messages`, `GET /api/v1/google/gmail/messages/{message_id}`, `GET /api/v1/google/calendar/events`, `POST /api/v1/google/calendar/events`, `GET /api/v1/todoist/tasks`, `POST /api/v1/todoist/tasks`, and `DELETE /api/v1/connections/{google|todoist|blueticks}`. Write endpoints perform the specific requested operation directly; keep them behind an explicit user action/confirmation in any AI workflow.

## Codex and ChatGPT Desktop MCP
The MCP bridge is in `mcp-server/server.py`. For local Codex, use stdio transport and the development-only identity described in [docs/CODEX_SETUP.md](docs/CODEX_SETUP.md). This avoids publishing an unauthenticated MCP endpoint. The bridge exposes backend health, integration status, connected-account status and assistant chat.

An optional local Streamable HTTP bridge can be started with `docker compose --profile mcp up --build mcp-server` at `http://localhost:8001/mcp`. Do not publish this unauthenticated development bridge to the public internet. Production requires a user-scoped OIDC bearer token and an authenticated transport/reverse proxy; never share one backend token among multiple users.

## Authentication
Production API bearer tokens are validated as RS256 JWTs using the configured OIDC issuer, audience and JWKS URL. The stable token subject is the per-user data partition key. Configure your identity provider to issue API access tokens with the expected audience. Local development's X-User-ID bypass is disabled outside APP_ENV=development.

## Live provider smoke test
After owner-configured OAuth and consent, run the read-only live integration checks in [the setup guide](docs/GOOGLE_TODOIST_SETUP.md) with `python scripts/live_integration_smoke.py`. It verifies Gmail, Calendar, Todoist, API health, and optionally Blueticks discovery without displaying private content or creating/modifying data.

## Worker reliability
The Redis worker atomically moves jobs to an in-flight list and requeues unacknowledged jobs after a worker process restart. Run exactly one worker replica with this recovery strategy. Production still needs Redis persistence/backup and restore validation; the queue is not a substitute for a durable transactional job broker.

## AWS
The Terraform directory is a foundation for VPC, ECR, ECS cluster, encrypted RDS with AWS-managed credentials, Redis, IAM roles, CloudWatch and ALB. It is not yet a complete deployable environment: ECS task definitions/services, WAF, ACM, autoscaling, application secret injection and operational alarms still need implementation and review. Review monthly costs before provisioning.

## Current limitations
- OIDC RS256 issuer/audience/JWKS validation is implemented for externally issued access tokens. Interactive login, account provisioning, provider-specific token revocation and identity-provider administration remain external setup tasks.
- The Redis worker handles queued OAuth token refresh and periodic expired-state cleanup with bounded retries, a dead-letter list, and recovery of in-flight jobs after process restarts when Redis retains its data. User-facing reminder/digest scheduling and Redis durability/restore validation remain outstanding.
- Live Blueticks discovery/tool execution still requires the owner to complete Blueticks OAuth consent in the dashboard and configure exact tool-scope allowlists. Google/Todoist API access requires their OAuth consent and provider app configuration.
- AWS infrastructure has not been applied. Docker and Terraform CLIs were not available in the current development environment.
- Configure TLS, WAF, rate limits, backups, restore tests, monitoring, secrets injection and security scans before production use.
