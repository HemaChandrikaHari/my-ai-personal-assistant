# Serverless AWS migration — preparation only

Target region: **Asia Pacific (Hyderabad), ap-south-2**.

## Budget and deployment guardrails

The required AWS spend limit is **INR 0/month**. This branch contains code and infrastructure definitions only. **No AWS resources have been created.** Do not run `sam deploy`, `aws cloudformation deploy`, `aws cloudformation create-stack`, or `terraform apply` without a new, explicit approval after reviewing the account plan, service eligibility, regional pricing and the full change set.

Free allowances are not a promise of zero cost. Cognito domains, API Gateway, DynamoDB provisioned throughput, Lambda, SQS, CloudWatch logs, data transfer, Amplify builds/hosting and Secrets Manager can have charges depending on account plan, usage and current offer. A budget is an alert, not a hard spending cap. The safest way to preserve INR 0 is not to create AWS resources.

## Architecture

| Capability | Target |
|---|---|
| Frontend | Next.js; Cognito Hosted UI authorization-code flow with PKCE |
| API | FastAPI + Mangum on Lambda; API Gateway HTTP API |
| Authentication | Cognito User Pool; JWT authorizer plus Lambda verification of ID token, issuer, audience and token_use |
| Persistence | DynamoDB tables for users, integrations, approvals, per-app permissions, audit and chat history |
| Background tasks | SQS Standard queue + dead-letter queue + Lambda event source |
| Operational logs | Lambda/CloudWatch (retention/cost review still required) |
| WhatsApp | Existing Blueticks MCP endpoint; runtime token only from Secrets Manager |
| AI | Disabled by default; optional external provider secret invokes paid model APIs |

## Implemented in this branch

- `template.yaml`: SAM template for Cognito, six DynamoDB tables, SQS and DLQ, Cognito-JWT-protected HTTP API, API Lambda and SQS worker. DynamoDB provisioned capacity is set to 1 RCU/1 WCU per table to stay below the commonly advertised 25/25 allowance in aggregate, but eligibility and all other costs must still be checked.
- `backend/app/serverless_app.py`: Cognito ID-token verification; DynamoDB operations for integration catalog, approvals, read/write/send grants, audit events and chat output; SQS enqueue; optional Blueticks MCP discovery/tool invocation; optional external AI provider configured through Secrets Manager. No provider secret means no AI model call.
- `backend/app/serverless_worker.py`: SQS batch handler with partial-batch failure response. It validates message shape and supported task types but deliberately performs no external side effects yet.
- `frontend/app/page.tsx`: Cognito Hosted UI authorization-code flow with PKCE, state verification, sessionStorage token handling, refresh-token exchange and sign-out.
- Legacy ECS/RDS/Redis Terraform remains for reference only. It is not the selected architecture and must not be applied for the INR 0 plan.

## Remaining blockers — not production-ready

1. **SAM validation/build:** AWS SAM CLI and CloudFormation validation have not been run. Template syntax parsing alone is not sufficient. Check every intrinsic, policy, route authorizer, packaging path and generated IAM role.
2. **SQS task handlers:** Worker currently validates then acknowledges supported task types without doing the task. Add concrete handlers, idempotency store, bounded retries, observability and authorization checks before enabling jobs.
3. **DynamoDB operational quality:** Add pagination for scan/query results, conditional/idempotent approval request creation, audit retention strategy and load/concurrency tests. Validate key design against actual access patterns.
4. **Cognito and frontend:** Set the Hosted UI domain prefix and exact callback/logout URLs. Configure matching frontend environment variables. Test sign-in, refresh, expiry, logout, CORS and 401 handling against a test user pool before use.
5. **Blueticks:** A separate AWS Secrets Manager secret is needed for the Lambda runtime. ChatGPT's existing Blueticks connector credentials are not available automatically to AWS. Do not overwrite or rotate the existing connection. Discover the actual tool catalogue and explicitly configure read/send allowlists; unknown tools default to write.
6. **AI:** The optional provider secret path can incur third-party model charges. Leave it empty under the INR 0 budget. Bedrock is not invoked.
7. **IAM and monitoring:** Review generated Lambda roles, reduce table permissions to only needed operations, add log retention, alarms and sensitive-data redaction.
8. **Frontend hosting:** Amplify is not configured or deployed. Verify account-plan eligibility, build minutes, bandwidth, storage and domain/DNS costs before use.
9. **Security testing:** Add rate limits, request size limits, CSRF review if cookies are introduced, CSP/security headers, dependency scanning, secret scanning, penetration tests and backup/restore procedures.
10. **Cost approval:** Review AWS Pricing Calculator estimates and account Free/Paid plan restrictions for ap-south-2. With a strict INR 0 limit, do not deploy if any resource has an unavoidable charge or uncertain eligibility.

## Local configuration for Cognito frontend

After an approved test deployment, configure these public (non-secret) build variables in the frontend hosting environment:

- `NEXT_PUBLIC_API_BASE_URL`: API Gateway URL
- `NEXT_PUBLIC_COGNITO_DOMAIN`: Cognito Hosted UI domain output
- `NEXT_PUBLIC_COGNITO_CLIENT_ID`: Cognito app client ID output
- `NEXT_PUBLIC_COGNITO_REDIRECT_URI`: exact registered callback URL, e.g. the local development origin

Do not put tokens, client secrets, Blueticks bearer tokens, AWS keys or provider API keys in `NEXT_PUBLIC_*` variables.

## Security

- Never commit AWS keys, Blueticks tokens, OAuth tokens, JWT signing secrets, `.env` files or Terraform state.
- Treat inbound WhatsApp messages, email, files, MCP tool output and model output as untrusted data.
- Identity comes from a cryptographically verified Cognito ID token `sub`; never accept caller-supplied user IDs.
- Keep read, write and send scopes separate. Discovery never grants consent.
- The existing Blueticks ChatGPT connector is separate from AWS runtime credentials.
- Do not deploy this template under the current INR 0 budget without explicit review and approval.
