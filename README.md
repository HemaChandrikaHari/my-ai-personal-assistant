# My AI Personal Assistant

A modular personal-assistant platform with a shared FastAPI backend, Next.js dashboard, ChatGPT-facing MCP interface, explicit per-integration approvals, and AWS deployment scaffolding.

## Core design
- FastAPI backend is the single source of truth for identity, permissions, integrations, workflows, and memory.
- Next.js dashboard and ChatGPT MCP server both use the same backend and authorization checks.
- Integrations are discovered and proposed automatically, but each app and each read/write/send scope requires explicit user approval.
- Existing WhatsApp connectivity is preserved through the Blueticks MCP endpoint configured as BLUETICKS_MCP_URL. Do not replace credentials or create a new WhatsApp connection.
- Credentials belong in AWS Secrets Manager, never in source control.

## Planned stack
FastAPI, Python, LangGraph, MCP, Next.js, PostgreSQL/pgvector, Redis workers, Docker Compose, AWS ECS Fargate, RDS, ElastiCache, Secrets Manager, Terraform.

## Security
Deny by default. Read permission does not imply write or send permission. Treat incoming messages and documents as untrusted content. Require confirmation for irreversible actions.

## Status
Initial project bootstrap. See docs/ for architecture, security, and AWS deployment guidance. Replace development authentication with OIDC/JWT and complete production hardening before deployment.
