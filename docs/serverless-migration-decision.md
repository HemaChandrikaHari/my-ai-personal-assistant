# Architecture decision: serverless migration

Status: **Accepted for implementation planning; not deployed.**

## Constraints
- Monthly AWS spending limit: ₹0.
- Preferred AWS region: ap-south-2 (Hyderabad).
- Preserve existing public repository and current Blueticks MCP connection.
- No AWS resource creation without explicit approval.

## Decision
Prepare a serverless design based on Cognito, Lambda + API Gateway, DynamoDB, SQS and CloudWatch. Defer Bedrock and ElastiCache. Treat Amplify as conditional on current account-plan eligibility and measured usage.

## Why
The existing ECS/RDS/Redis starter includes continuously billed infrastructure such as NAT Gateway, RDS, ElastiCache and ALB. The serverless option can reduce idle compute but does not guarantee zero charges. DynamoDB requires a deliberate data model and repository rewrite; it is not a PostgreSQL-compatible drop-in.

## Rollout
1. Design and local tests only.
2. Implement DynamoDB repositories and Cognito JWT verification.
3. Add Lambda/Mangum packaging and API Gateway route authorization.
4. Add SQS worker, retries and DLQ.
5. Review cost and account eligibility.
6. Only then consider deployment with user approval.

## Rollback
Keep the current relational implementation and existing Terraform starter on the existing main branch. Work on a feature branch; do not destroy or modify any live AWS resources.
