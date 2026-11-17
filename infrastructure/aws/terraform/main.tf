data "aws_availability_zones" "available" {
  state = "available"
}
locals {
  name = var.project
  tags = {
    Project   = local.name
    ManagedBy = "Terraform"
  }
}
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  name    = local.name
  cidr    = var.vpc_cidr
  azs     = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = ["10.42.1.0/24", "10.42.2.0/24"]
  public_subnets  = ["10.42.101.0/24", "10.42.102.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = true
  enable_dns_hostnames = true
  tags = local.tags
}
resource "aws_ecr_repository" "backend" {
  name = "${local.name}-backend"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  tags = local.tags
}
resource "aws_ecr_repository" "frontend" {
  name = "${local.name}-frontend"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  tags = local.tags
}
resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.tags
}
resource "aws_security_group" "app" {
  name_prefix = "${local.name}-app-"
  description = "Application task security group"
  vpc_id = module.vpc.vpc_id
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 8000
    to_port = 8000
    protocol = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  tags = local.tags
}
resource "aws_security_group_rule" "app_from_alb" {
  type = "ingress"
  security_group_id = aws_security_group.app.id
  source_security_group_id = aws_security_group.alb.id
  from_port = 8000
  to_port = 8000
  protocol = "tcp"
}
resource "aws_security_group" "database" {
  name_prefix = "${local.name}-db-"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port = 5432
    to_port = 5432
    protocol = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_db_subnet_group" "main" {
  name = "${local.name}-db"
  subnet_ids = module.vpc.private_subnets
  tags = local.tags
}
resource "aws_db_instance" "main" {
  identifier = "${local.name}-postgres"
  engine = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"
  allocated_storage = 20
  max_allocated_storage = 100
  db_name = var.db_name
  username = var.db_username
  manage_master_user_password = true
  storage_encrypted = true
  publicly_accessible = false
  multi_az = false
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  backup_retention_period = 7
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${local.name}-final"
  tags = local.tags
}
resource "aws_elasticache_subnet_group" "main" {
  name = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets
}
resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port = 6379
    to_port = 6379
    protocol = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name}-redis"
  description = "Assistant Redis cache and queue"
  node_type = "cache.t4g.micro"
  num_cache_clusters = 1
  engine = "redis"
  engine_version = "7.1"
  port = 6379
  subnet_group_name = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  automatic_failover_enabled = false
  tags = local.tags
}
resource "aws_cloudwatch_log_group" "backend" {
  name = "/ecs/${local.name}/backend"
  retention_in_days = 30
  tags = local.tags
}
resource "aws_cloudwatch_log_group" "frontend" {
  name = "/ecs/${local.name}/frontend"
  retention_in_days = 30
  tags = local.tags
}
resource "aws_iam_role" "task_execution" {
  name = "${local.name}-task-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}
resource "aws_iam_role_policy_attachment" "task_execution" {
  role = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role" "task" {
  name = "${local.name}-task"
  assume_role_policy = aws_iam_role.task_execution.assume_role_policy
  tags = local.tags
}
resource "aws_iam_role_policy" "task_secrets" {
  name = "read-managed-db-secret"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = aws_db_instance.main.master_user_secret[0].secret_arn
    }]
  })
}
resource "aws_lb" "api" {
  name = "${local.name}-api"
  load_balancer_type = "application"
  subnets = module.vpc.public_subnets
  security_groups = [aws_security_group.alb.id]
  tags = local.tags
}
resource "aws_lb_target_group" "backend" {
  name = "${local.name}-api"
  port = 8000
  protocol = "HTTP"
  vpc_id = module.vpc.vpc_id
  target_type = "ip"
  health_check {
    path = "/health"
    matcher = "200"
  }
}
resource "aws_lb_listener" "https" {
  count = var.certificate_arn == "" ? 0 : 1
  load_balancer_arn = aws_lb.api.arn
  port = 443
  protocol = "HTTPS"
  certificate_arn = var.certificate_arn
  default_action {
    type = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}
