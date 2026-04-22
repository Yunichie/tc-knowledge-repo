# TC Knowledge Repo — Backend

## Tech Stack

| Layer | Stack |
|-------|------------|
| Framework | Django 5.x + Django Ninja |
| Database | PostgreSQL 16 (Neon in production) |
| Task Queue | Celery 5.x + Redis 7.x |
| Storage | Cloudflare R2 |
| Package Manager | `uv` |

## Quick Start (Local Development)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (for local Python dev)

### 1. Clone & Configure

```bash
git clone <repo-url>
cd tc-knowledge-repo
cp .env.example .env
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

This starts four services:
- **db** - PostgreSQL 16 on `localhost:5432`
- **redis** - Redis 7 on `localhost:6379`
- **api** - Django API on `http://localhost:8000`
- **worker** - Celery background worker

### 3. Initial Setup

```bash
# Run migrations (auto-runs on compose up, but just in case)
docker compose exec api python manage.py migrate

# Create a superuser for Django admin
docker compose exec api python manage.py createsuperuser
```


### Local Development Without Docker

```bash
uv sync                                     # Install dependencies
uv run python manage.py migrate             # Run migrations
uv run python manage.py runserver           # Start API
uv run celery -A config worker --loglevel=info  # Start worker (separate terminal)
```

> **Note:** Need a local PostgreSQL and Redis running, or update `DATABASE_URL` and `REDIS_URL` in `.env`.
