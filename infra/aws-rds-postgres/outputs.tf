output "db_instance_id" {
  description = "RDS instance ID."
  value       = aws_db_instance.postgres.id
}

output "db_instance_arn" {
  description = "RDS instance ARN."
  value       = aws_db_instance.postgres.arn
}

output "db_endpoint" {
  description = "RDS endpoint hostname."
  value       = aws_db_instance.postgres.address
}

output "db_port" {
  description = "RDS endpoint port."
  value       = aws_db_instance.postgres.port
}

output "db_name" {
  description = "Database name provisioned on the RDS instance."
  value       = var.db_name
}

output "db_security_group_id" {
  description = "Security group attached to the RDS instance."
  value       = aws_security_group.postgres.id
}

output "secret_arn" {
  description = "Secrets Manager ARN containing database credentials and URLs."
  value       = aws_secretsmanager_secret.postgres.arn
}

output "secret_name" {
  description = "Secrets Manager name containing database credentials and URLs."
  value       = aws_secretsmanager_secret.postgres.name
}
