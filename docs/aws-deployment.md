# AWS deployment
Target: CloudFront/WAF → ALB → ECS Fargate services (frontend, API, worker, MCP) → RDS PostgreSQL and ElastiCache Redis. Use ECR for images, Secrets Manager for credentials, CloudWatch for logs/metrics, S3 for assets/backups, ACM for TLS.

Provision a VPC with private app/data subnets, encrypted RDS, Redis, least-privilege task roles, ECR, ECS services, ALB health checks, domain/TLS, WAF, alarms, backups and restore testing. Configure remote encrypted Terraform state. Run schema migrations as a one-off task. Review cost and security before applying.
