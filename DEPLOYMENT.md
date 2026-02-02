Deployment Quickstart

Environment
- Copy `.env.example` to `.env` and set `SECRET_KEY`.
- If using Postgres, set `DATABASE_URL` to your connection string.

One-time DB init
- `flask --app app.py init-db` (set `SEED_DB=true` if you want seed data)

Migrations
- `flask --app app.py db migrate -m "describe change"`
- `flask --app app.py db upgrade`

Docker
- Copy `.env.example` to `.env` and set a strong `SECRET_KEY`.
- Build and run: `docker compose up --build -d`
- Initialize DB (one-time): `docker compose run --rm web flask --app app.py init-db`
- App listens on `http://localhost:8000`

AWS EC2 (Docker + SQLite + Nginx)
- Install Docker and the Compose plugin on the instance.
- Create a persistent data directory for SQLite:
  - `mkdir -p ~/elf-ai/data`
  - `sudo chown -R 1000:1000 ~/elf-ai/data`
- Copy the repo to the instance and create `.env` from `.env.example` with a strong `SECRET_KEY`.
- Build and run the production stack:
  - `docker compose -f docker-compose.prod.yml up --build -d`
- Initialize the DB (one-time):
  - `docker compose -f docker-compose.prod.yml run --rm web flask --app app.py init-db`
- Open inbound port 80 in the EC2 Security Group.

HTTPS (Let's Encrypt + Nginx)
- Point your domain's DNS A record to the EC2 public IP.
- Temporarily use the HTTP-only config for the initial cert:
  - Edit `docker-compose.prod.yml` to mount `./nginx/elf-ai-http.conf` as `default.conf`.
  - `docker compose -f docker-compose.prod.yml up -d`
- Request the cert (replace values):
  - `docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d your-domain.com -d www.your-domain.com --email you@example.com --agree-tos --no-eff-email`
- Switch back to the SSL config:
  - Edit `docker-compose.prod.yml` to mount `./nginx/elf-ai.conf` as `default.conf`.
  - Update `nginx/elf-ai.conf` to use your domain in the cert paths.
  - `docker compose -f docker-compose.prod.yml up -d`
- Renewal (run monthly via cron):
  - `docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot`
  - `docker compose -f docker-compose.prod.yml exec nginx nginx -s reload`

GitHub Quickstart
- `git init`
- `git add .`
- `git commit -m "Initial commit"`
- Create a new GitHub repo and set the remote:
  - `git remote add origin <your-repo-url>`
  - `git branch -M main`
  - `git push -u origin main`

Gunicorn (no Docker)
- `gunicorn wsgi:app -c gunicorn.conf.py`

Health check
- `GET /healthz`
