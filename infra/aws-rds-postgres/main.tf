locals {
  base_name              = lower("${var.name_prefix}-${var.environment}")
  db_identifier          = "${local.base_name}-postgres"
  db_subnet_group_name   = "${local.base_name}-db-subnets"
  db_security_group_name = "${local.base_name}-db-sg"
  secret_name            = var.secret_name_override != "" ? var.secret_name_override : "${var.name_prefix}/${var.environment}/postgres"
  has_ingress_sources    = length(var.app_security_group_ids) > 0 || length(var.allowed_cidr_blocks) > 0
  common_tags = merge(
    {
      Project     = var.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

check "db_ingress_sources_configured" {
  assert {
    condition     = local.has_ingress_sources
    error_message = "Provide at least one source in app_security_group_ids or allowed_cidr_blocks for Postgres access."
  }
}

resource "random_password" "db_master" {
  length  = 32
  special = false
}

resource "random_id" "final_snapshot_suffix" {
  byte_length = 4
}

resource "aws_db_subnet_group" "postgres" {
  name       = local.db_subnet_group_name
  subnet_ids = var.private_subnet_ids
  tags = merge(local.common_tags, {
    Name = local.db_subnet_group_name
  })
}

resource "aws_security_group" "postgres" {
  name        = local.db_security_group_name
  description = "Postgres access for ${local.db_identifier}"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name = local.db_security_group_name
  })
}

resource "aws_security_group_rule" "postgres_ingress_from_app_sg" {
  for_each = toset(var.app_security_group_ids)

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.postgres.id
  source_security_group_id = each.value
  description              = "Allow Postgres from app SG ${each.value}"
}

resource "aws_security_group_rule" "postgres_ingress_from_cidr" {
  for_each = toset(var.allowed_cidr_blocks)

  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  security_group_id = aws_security_group.postgres.id
  cidr_blocks       = [each.value]
  description       = "Allow Postgres from ${each.value}"
}

resource "aws_security_group_rule" "postgres_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.postgres.id
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_db_instance" "postgres" {
  identifier                  = local.db_identifier
  engine                      = "postgres"
  engine_version              = var.engine_version
  instance_class              = var.db_instance_class
  allocated_storage           = var.allocated_storage
  max_allocated_storage       = var.max_allocated_storage
  storage_type                = "gp3"
  storage_encrypted           = var.storage_encrypted
  db_name                     = var.db_name
  username                    = var.db_username
  password                    = random_password.db_master.result
  port                        = 5432
  multi_az                    = var.multi_az
  publicly_accessible         = var.publicly_accessible
  db_subnet_group_name        = aws_db_subnet_group.postgres.name
  vpc_security_group_ids      = [aws_security_group.postgres.id]
  backup_retention_period     = var.backup_retention_period
  deletion_protection         = var.deletion_protection
  apply_immediately           = var.apply_immediately
  auto_minor_version_upgrade  = true
  skip_final_snapshot         = var.skip_final_snapshot
  final_snapshot_identifier   = var.skip_final_snapshot ? null : "${local.db_identifier}-final-${random_id.final_snapshot_suffix.hex}"
  copy_tags_to_snapshot       = true

  tags = merge(local.common_tags, {
    Name = local.db_identifier
  })
}

resource "aws_secretsmanager_secret" "postgres" {
  name                    = local.secret_name
  recovery_window_in_days = var.secret_recovery_window_in_days
  tags = merge(local.common_tags, {
    Name = local.secret_name
  })
}

resource "aws_secretsmanager_secret_version" "postgres" {
  secret_id = aws_secretsmanager_secret.postgres.id
  secret_string = jsonencode({
    engine                    = "postgres"
    host                      = aws_db_instance.postgres.address
    port                      = aws_db_instance.postgres.port
    dbname                    = var.db_name
    username                  = var.db_username
    password                  = random_password.db_master.result
    sslmode                   = "require"
    sqlalchemy_database_url   = "postgresql+psycopg2://${var.db_username}:${random_password.db_master.result}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${var.db_name}?sslmode=require"
    standard_database_url     = "postgresql://${var.db_username}:${random_password.db_master.result}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${var.db_name}?sslmode=require"
  })
}
