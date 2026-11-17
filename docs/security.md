# Security checklist
- Replace development x-user-id header with OIDC/JWT validation.
- Deny by default; check user + integration + scope on every action.
- Keep read, write and send grants independent; confirm irreversible actions.
- Store credentials in AWS Secrets Manager; persist only secret ARNs/references.
- Allowlist remote MCP hosts and defend against SSRF, redirects and private IP targets.
- Add audit logs, idempotency keys, rate limits, replay protection and tenant isolation.
- Encrypt transport, database and backups; use least-privilege IAM.
- Treat messages and documents as untrusted prompt content. Never log secrets.
