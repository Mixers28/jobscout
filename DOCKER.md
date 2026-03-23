# Docker Setup — JobScout Copilot

## Prerequisites

**Option A — Docker Desktop (Windows/Mac)**
Download and install from https://www.docker.com/products/docker-desktop/

**Option B — Docker Engine in WSL2 (Ubuntu)**
```bash
# Remove any conflicting packages
sudo apt-get remove -y docker-compose-v2

# Add Docker's official repo
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start daemon and add your user (re-open terminal after)
sudo service docker start
sudo usermod -aG docker $USER
```

> WSL2 note: Docker doesn't auto-start on boot. Add this to `~/.bashrc` to start it automatically:
> ```bash
> sudo service docker start > /dev/null 2>&1
> ```

---

## First-time setup

```bash
cp .env.example .env
```

Edit `.env` if you want notifications:
- `JOBSCOUT_DISCORD_WEBHOOK_URL` — Discord webhook for job alerts
- `JOBSCOUT_IMAP_*` — Gmail credentials to ingest job-alert emails
- `JOBSCOUT_SMTP_*` — SMTP fallback for email notifications

---

## Starting the app

```bash
docker compose up --build
```

This starts all services:

| Service   | Description                        |
|-----------|------------------------------------|
| postgres  | Database (persistent volume)       |
| redis     | Queue / cache                      |
| api       | FastAPI backend — runs migrations on first boot |
| worker    | Scheduler / ingest / scoring       |
| web       | Next.js dashboard                  |

Once running:
- **Dashboard:** http://localhost:3001
- **Ops Console:** http://localhost:3001/ops
- **API:** http://localhost:8001

---

## Common commands

```bash
# Start in background (detached)
make docker-up

# Stop and remove containers
make docker-down

# Tail all logs
make docker-logs

# Run DB migrations manually (only needed if you skipped first boot)
make docker-migrate
```

Or using `docker compose` directly:

```bash
docker compose up --build          # foreground, rebuild images
docker compose up --build -d       # background
docker compose down                # stop + remove containers
docker compose down -v             # stop + remove containers AND volumes (wipes DB)
docker compose logs -f             # tail all logs
docker compose logs -f api         # tail a single service
docker compose restart worker      # restart one service
docker compose exec api bash       # shell into a container
```

---

## Services and ports

| Service  | Host port | Internal URL (container-to-container) |
|----------|-----------|----------------------------------------|
| API      | 8001      | `http://api:8000`                      |
| Web UI   | 3001      | `http://web:3000`                      |
| Postgres | —         | `postgres:5432`                        |
| Redis    | —         | `redis:6379`                           |

Postgres and Redis are not exposed to the host by default.

---

## Running a scheduled cycle manually

```bash
docker compose exec worker python -m worker.main --schedule-once
```

---

## Resetting everything

```bash
docker compose down -v    # removes containers + the postgres_data volume
docker compose up --build
```

This gives you a clean slate with a fresh database.
