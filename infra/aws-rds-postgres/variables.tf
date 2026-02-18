variable "aws_region" {
  description = "AWS region where RDS and Secrets Manager resources are provisioned."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Project prefix used in resource names and tags."
  type        = string
  default     = "elf-ai"
}

variable "environment" {
  description = "Environment label, for example dev, stage, or prod."
  type        = string
  default     = "prod"
}

variable "vpc_id" {
  description = "VPC ID where the database should be created."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the DB subnet group."
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Provide at least two subnet IDs in different AZs for RDS."
  }
}

variable "app_security_group_ids" {
  description = "Security group IDs allowed to connect to Postgres on 5432."
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to Postgres on 5432."
  type        = list(string)
  default     = []
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "elfai"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,62}$", var.db_name))
    error_message = "db_name must start with a letter and contain only letters, numbers, and underscores."
  }
}

variable "db_username" {
  description = "Master username for the Postgres instance."
  type        = string
  default     = "elfai_admin"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,62}$", var.db_username))
    error_message = "db_username must start with a letter and contain only letters, numbers, and underscores."
  }
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "engine_version" {
  description = "Postgres engine version. Set to null for AWS default."
  type        = string
  default     = null
}

variable "allocated_storage" {
  description = "Initial storage allocation in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum autoscaled storage in GiB."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Enable Multi-AZ deployment."
  type        = bool
  default     = false
}

variable "publicly_accessible" {
  description = "Whether RDS should receive a public IP. Keep false for private deployments."
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "Number of days to retain automated backups."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Block accidental RDS deletion."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot when destroying the DB instance."
  type        = bool
  default     = false
}

variable "apply_immediately" {
  description = "Apply modifications immediately instead of waiting for maintenance window."
  type        = bool
  default     = false
}

variable "storage_encrypted" {
  description = "Enable encryption at rest for RDS storage."
  type        = bool
  default     = true
}

variable "secret_name_override" {
  description = "Custom secret name. Leave empty to use name_prefix/environment convention."
  type        = string
  default     = ""
}

variable "secret_recovery_window_in_days" {
  description = "Recovery window for deleting the generated secret."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}
