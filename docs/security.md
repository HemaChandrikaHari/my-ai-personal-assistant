# Security status and checklist

Implemented in the development foundation:
- JWT HS256 verification with required subject and expiry claims outside development.
- Development-only X-User-ID shim; never enable it on a public deployment.
- Per-user, per-integration, per-scope grants. Read does not imply write or send.
- Explicit approval requests and audit events.
- Blueticks host allowlist and runtime-only bearer token injection.
- Unknown tools default to write; exact read-only and send allowlists are configuration-controlled.
- ChatGPT MCP bridge does not expose arbitrary write/send tools.

Required before production:
- Integrate a real OIDC provider, issuer/audience validation, key rotation and refresh/revocation strategy.
- Use AWS Secrets Manager for OpenAI and Blueticks credentials; inject through least-privilege task roles.
- Add request rate limits, CSRF protection where cookie auth is used, structured audit retention and tenant isolation.
- Add idempotency/replay protection for mutations and approval concurrency controls.
- Add TLS, WAF, private subnet routing, DB backups and restore tests.
- Use Alembic migrations; never rely on create_all in production.
- Conduct dependency, container, Terraform and application security scans.

Never commit environment files, API keys, tokens, private keys, database passwords or Terraform state.
