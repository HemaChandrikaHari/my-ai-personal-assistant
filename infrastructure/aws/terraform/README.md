# AWS Terraform starter

This is a foundation, not a complete deployable environment. It provisions a VPC, private database/cache subnets, encrypted RDS PostgreSQL with AWS-managed master credentials, Redis, ECR repositories, ECS cluster, CloudWatch log groups, task roles, and an ALB.

Before deployment:
- Review every resource and estimated cost. NAT Gateway, RDS, Redis and ALB incur ongoing charges.
- Configure encrypted remote Terraform state with locking; never commit state.
- Add ECS task definitions/services, target groups, ALB listener and ACM certificate, WAF, autoscaling, alarms, and secret injection for application secrets.
- Store OpenAI and Blueticks runtime credentials in Secrets Manager; do not put values in variables or Terraform state.
- Run `terraform fmt -check`, `terraform validate`, and a reviewed `terraform plan`.
- Do not apply until network access, IAM, TLS, backups, disaster recovery and monthly cost are reviewed.

RDS master credentials are generated and managed by AWS Secrets Manager. No password is defined in Terraform variables.
