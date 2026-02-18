# AWS RDS PostgreSQL Infrastructure

This Terraform stack provisions:

- 1 x Amazon RDS PostgreSQL instance
- 1 x DB subnet group in your private subnets
- 1 x security group for database access on port `5432`
- 1 x Secrets Manager secret containing DB credentials and connection URLs

## Prerequisites

- Terraform `>= 1.5`
- AWS credentials with permission to create RDS, EC2 security groups, and Secrets Manager resources
- Existing VPC + private subnets for the DB
- Security group for your app/EC2 instance

## Usage

```bash
cd infra/aws-rds-postgres
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your VPC/subnet/SG IDs
terraform init
terraform plan
terraform apply
```

## Outputs

After apply, note:

- `secret_arn`
- `secret_name`
- `db_endpoint`

Use `secret_arn` or `secret_name` with `scripts/sync-rds-env.sh` to update `.env` on the EC2 host.
