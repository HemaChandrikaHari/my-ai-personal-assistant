# Serverless AWS migration — preparation only

Target region: **Asia Pacific (Hyderabad), `ap-south-2`**.

## Non-negotiable budget constraint

The owner's AWS deployment budget is **₹0/month**. This directory is an infrastructure design and validation starting point only. **Do not deploy this template or run `sam deploy`, `aws cloudformation deploy`, or `terraform apply` without a fresh explicit approval after checking the account's current Free/Paid plan and each resource's regional pricing.** Even services described as having a free tier can become billable when allowances expire or are exceeded. Free-tier eligibility, service availability and quotas vary by account, region and date.

No AWS resources have been created by preparing these files.

## Proposed mapping

| Existing capability | Serverless target |
|---|---|
| Next.js dashboard | Amplify Hosting (only after verifying current account-plan eligibility and build/storage/bandwidth charges) |
| FastAPI | Lambda + Mangum + API Gateway HTTP API |
| Authentication | Cognito User Pool; API Gateway JWT authorizer |
| PostgreSQL | DynamoDB (requires an application data-access rewrite; this is not a drop-in replacement) |
| Redis queue | SQS Standard queue + dead-letter queue |
| Audit history | DynamoDB AuditLogs; CloudWatch for operational logs |
| Per-app grants | DynamoDB AppPermissions with distinct read/write/send permissions |
| WhatsApp | Existing Blueticks MCP endpoint, invoked server-side only after runtime authentication and tool-scope review |
| AI provider | Disabled by default; no Bedrock invocation in the zero-spend configuration |

## Files

- `template.yaml`: CloudFormation/SAM resource foundation for Cognito, four DynamoDB tables, SQS queues and an HTTP API with a Cognito JWT authorizer. It deliberately does not contain a Lambda integration or deployable application handler yet.
- `../terraform`: legacy ECS/RDS/Redis infrastructure starter. Retained for reference; it is not the target architecture and must not be applied for the ₹0 plan.

## Important implementation gap

The current FastAPI application uses SQLAlchemy models and a relational database. Simply adding Mangum or changing a connection string will not make it work with DynamoDB. The API must be refactored behind a repository/data-access layer, preserving per-user isolation, approval state transitions, audit records, idempotency and the existing HTTP contracts. Then a Lambda adapter and API Gateway routes must be added and tested. The SAM template is not a complete application deployment.

## Required work before any deployment

1. Confirm AWS account type (Free vs Paid) and that required services are permitted in `ap-south-2`.
2. Verify current free allowances and regional pricing for Cognito, DynamoDB provisioned capacity, SQS, Lambda, API Gateway, CloudWatch and Amplify. Do not assume old free-tier tables still apply.
3. Set billing notifications and Free Tier alerts. Budgets are alerts, not hard spend caps.
4. Implement and test the DynamoDB repository layer and Lambda handler locally.
5. Add API routes with JWT authorizer on every protected route. The API Gateway authorizer must be explicitly attached to routes; defining it alone does not protect them.
6. Implement least-privilege Lambda IAM policies for only the four tables and the specific SQS queue.
7. Add request throttling, payload limits, CORS allowlist, structured logs with sensitive-data redaction, retries/DLQ handling, idempotency and data-retention policies.
8. Add Amplify build configuration only after cost/plan review.
9. Validate with SAM/CloudFormation lint and a change set. A change set is not permission to execute it.
10. Obtain explicit approval before creating any resources.

## Security notes

- Never commit AWS keys, Blueticks tokens, OAuth tokens, JWT signing secrets, `.env` files or Terraform state.
- Never treat inbound WhatsApp messages, email, files, MCP tool output or model output as trusted instructions.
- Derive the user identity from a cryptographically verified Cognito JWT `sub`; never accept a caller-supplied `userId` as identity.
- Keep read, write and send scopes separate. Discovery must never imply consent.
- The existing Blueticks ChatGPT connector is separate from credentials available to a Lambda runtime. Do not overwrite, rotate or recreate the existing connection.
