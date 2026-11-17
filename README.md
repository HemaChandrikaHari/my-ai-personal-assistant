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
The existing endpoint remains https://api.blueticks.co/mcp. Discovery is explicit and does not grant access. Tool invocation requires a separately approved read, write or send scope. Set BLUETICKS_READ_ONLY_TOOLS and BLUETICKS_SEND_TOOLS to exact tool names after inspecting capabilities. Unknown tools default to write permission. Credentials are read from runtime environment only; use AWS Secrets Manager in deployment. Existing Blueticks credentials are not stored in this repository or copied from ChatGPT's separate connection.

## ChatGPT MCP
The restricted bridge is in mcp-server/server.py. Run it with docker compose --profile mcp up --build mcp-server after supplying a short-lived, user-scoped ASSISTANT_BACKEND_TOKEN. The bridge exposes health, integration listing and assistant chat only. Do not share one backend token among multiple users.

## AWS deployment (₹0/month target)
The preferred deployment direction is a serverless design documented in `infrastructure/aws/serverless/README.md`: Cognito, Lambda + API Gateway, DynamoDB, SQS and CloudWatch, with Amplify conditional on account-plan eligibility and usage costs. The serverless CloudFormation/SAM template is a resource foundation only; it does not yet include a working Lambda integration or DynamoDB-backed application implementation. **Do not deploy it until current Free/Paid plan eligibility, regional pricing, quotas and the complete change set are reviewed. No AWS resources have been created.**

The older ECS/RDS/Redis Terraform starter remains under `infrastructure/aws/terraform` for reference only. It includes continuously billable infrastructure such as NAT Gateway, RDS, ElastiCache and ALB and must not be applied for the ₹0/month plan. Its default region is set to `ap-south-2` (Hyderabad), but the configuration is not the selected target.

## Current limitations
- Real OIDC, issuer/audience validation, token refresh/revocation and multi-user identity mapping are not yet implemented.
- The Redis worker is a safe queue skeleton; concrete task handlers, retries with backoff and scheduler are not yet implemented.
- Live Blueticks discovery/tool execution requires the runtime credentials and exact tool-scope allowlists configured by the owner.
- AWS infrastructure has not been applied. Docker and Terraform CLIs were not available in the current development environment.
- Configure TLS, WAF, rate limits, backups, restore tests, monitoring, secrets injection and security scans before production use.
