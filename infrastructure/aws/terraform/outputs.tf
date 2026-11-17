output "vpc_id" { value = module.vpc.vpc_id }
output "backend_ecr_url" { value = aws_ecr_repository.backend.repository_url }
output "frontend_ecr_url" { value = aws_ecr_repository.frontend.repository_url }
output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "rds_endpoint" { value = aws_db_instance.main.address }
output "rds_managed_secret_arn" { value = aws_db_instance.main.master_user_secret[0].secret_arn }
output "redis_primary_endpoint" { value = aws_elasticache_replication_group.main.primary_endpoint_address }
output "alb_dns_name" { value = aws_lb.api.dns_name }
