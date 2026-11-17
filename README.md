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

## AWS deployment (INR 0/month target)
The serverless migration is being prepared on branch `feat/serverless-aws`. It includes Cognito Hosted UI with PKCE, Lambda + API Gateway, DynamoDB, SQS and an API/worker implementation. See `infrastructure/aws/serverless/README.md` for the current design and explicit blockers. **No AWS resources have been created. Do not deploy until AWS SAM validation/build, security review, account-plan eligibility and regional pricing have all been checked.** A Free Tier allowance is not a guarantee of zero charges.

The older ECS/RDS/Redis Terraform starter remains under `infrastructure/aws/terraform` for reference only. It includes potentially continuously billable NAT Gateway, RDS, ElastiCache and ALB resources and must not be applied for the INR 0/month plan. The serverless template targets `ap-south-2` (Hyderabad).

## Current limitations
- SAM CLI/CloudFormation validation and a Lambda packaging build have not been run.
- The SQS worker validates supported message types but intentionally performs no external task actions yet.
- Cognito Hosted UI and token refresh require live integration testing with a provisioned test pool and matching callback/logout URLs.
- Blueticks requires a separately configured AWS Secrets Manager runtime secret; ChatGPT connector credentials do not transfer to AWS. Exact tool-scope allowlists must be reviewed.
- AI provider invocation is disabled by default. Configuring a provider secret can incur third-party charges.
- Amplify hosting is not configured; account-plan eligibility and hosting/build/bandwidth costs must be reviewed.
- Configure throttling, payload limits, log retention, alarms, backup/restore and security scans before production use.
