Deployment Runbook (EC2 Ubuntu + Docker + RDS PostgreSQL)

1. Prerequisites
- Domain DNS A records for `elf-ai.co.za` and `www.elf-ai.co.za` pointing to the EC2 public IP.
- EC2 security group inbound rules:
  - `22/tcp` from your admin IP.
  - `80/tcp` from `0.0.0.0/0`.
  - `443/tcp` from `0.0.0.0/0`.
- IAM role on EC2 allowing:
  - `secretsmanager:GetSecretValue`
  - `kms:Decrypt` (for the Secrets Manager KMS key, if custom)
- RDS PostgreSQL secret in AWS Secrets Manager (or provision with Terraform below).

2. Optional: Provision RDS with Terraform
```bash
cd infra/aws-rds-postgres
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: vpc_id, private_subnet_ids, app_security_group_ids, db settings
terraform init
terraform plan
terraform apply
```
Save the `secret_arn` output for deployment steps.

3. Connect to EC2
```bash
chmod 400 /path/to/your-key.pem
ssh -i /path/to/your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

4. Install Docker Engine + Compose plugin on Ubuntu
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git awscli
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
newgrp docker
docker --version
docker compose version
```

5. Pull application code
```bash
cd /home/ubuntu
git clone <YOUR_GIT_REMOTE_URL> Elf-AI-Website
cd Elf-AI-Website
```

6. Create runtime env
```bash
cp .env.example .env
python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
```
Update `.env`:
- Set `SECRET_KEY=<generated value>`
- Set `SITE_URL=https://elf-ai.co.za`
- Keep `APP_ENV=production`

7. Populate `DATABASE_URL` from Secrets Manager
```bash
cd /home/ubuntu/Elf-AI-Website
export AWS_REGION=us-east-1
export RDS_SECRET_ID=<secret-arn-or-name>
ENV_FILE=.env ./scripts/sync-rds-env.sh "$RDS_SECRET_ID"
```

8. First-time production deploy (recommended one-command path)
```bash
cd /home/ubuntu/Elf-AI-Website
chmod +x scripts/ec2-bootstrap.sh scripts/sync-rds-env.sh
DOMAIN=elf-ai.co.za \
EMAIL=you@example.com \
AWS_REGION=us-east-1 \
RDS_SECRET_ID=<secret-arn-or-name> \
./scripts/ec2-bootstrap.sh
```
What this does:
- Validates Docker/Compose availability.
- Ensures `.env` exists and has a strong `SECRET_KEY`.
- Syncs `DATABASE_URL` from Secrets Manager if `RDS_SECRET_ID` is set.
- Boots HTTP Nginx for ACME challenge if no cert exists.
- Issues Let's Encrypt cert.
- Starts HTTPS Nginx + web app.
- Runs `flask db upgrade`.

9. Validate deployment
```bash
cd /home/ubuntu/Elf-AI-Website
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 web
docker compose -f docker-compose.prod.yml logs --tail=100 nginx
curl -I http://localhost/healthz
curl -I https://elf-ai.co.za/healthz
```

10. Subsequent deployments (code updates)
```bash
cd /home/ubuntu/Elf-AI-Website
git pull origin main
# optional if DB credentials rotated:
ENV_FILE=.env AWS_REGION=us-east-1 ./scripts/sync-rds-env.sh <secret-arn-or-name>
NGINX_CONF=elf-ai.conf docker compose -f docker-compose.prod.yml up --build -d web nginx
docker compose -f docker-compose.prod.yml run --rm web flask --app app.py db upgrade
docker compose -f docker-compose.prod.yml ps
```

11. Set certificate auto-renewal (cron)
```bash
crontab -e
```
Add:
```cron
0 3 * * * cd /home/ubuntu/Elf-AI-Website && docker compose -f docker-compose.prod.yml --profile ops run --rm certbot renew --webroot -w /var/www/certbot && NGINX_CONF=elf-ai.conf docker compose -f docker-compose.prod.yml exec nginx nginx -s reload >> /home/ubuntu/cert-renew.log 2>&1
```

12. Troubleshooting
```bash
# Container status and logs
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx

# Disk pressure (common Docker failure)
df -h
docker system df
docker image prune -f
docker builder prune -f

# Rebuild stack cleanly
NGINX_CONF=elf-ai.conf docker compose -f docker-compose.prod.yml down
NGINX_CONF=elf-ai.conf docker compose -f docker-compose.prod.yml up --build -d web nginx
```

13. Security checklist
- Do not store private SSH keys (`*.pem`) in the repo.
- Keep `.env` server-local only.
- Restrict SSH to your IP in the EC2 security group.
- Rotate DB credentials in Secrets Manager, then re-run `sync-rds-env.sh`.
- Keep Ubuntu packages and Docker up to date.
