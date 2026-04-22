# AGENTS.md

Instructions for AI agents working on this codebase.

## Project

Backend API for a college knowledge-sharing platform. Django + Django Ninja, Celery + Redis, PostgreSQL (Neon in prod), Cloudflare R2 for object storage.

**The frontend is NOT in this repo.** We only own the backend, API, workers, and infrastructure.

## Architecture

3-app split with one-way dependencies:

```
resources/  ← core app (Resource, Category, Tag, BulkDownload)
requests/   ← depends on resources (ResourceRequest)
reports/    ← depends on resources (Report)
```

`requests` and `reports` may import from `resources`. `resources` MUST NOT import from `requests` or `reports`.

## Tech Stack (Locked)

- Python 3.12, Django 5.x, Django Ninja (Pydantic schemas)
- Celery 5.x + Redis 7.x (task queue)
- PostgreSQL 16 (Neon serverless in prod)
- Cloudflare R2 (S3-compatible, boto3)
- `uv` for dependency management
- Docker + Docker Compose for local dev

## Conventions

### Code Style
- Use `ruff` for linting (config in `pyproject.toml`)
- Keep comments minimal and non-obvious. Do not write decorative separators or section banners.
- Do not prefix docstrings with the module/class name (e.g., write the purpose directly).
- Use concise docstrings. Omit them entirely for self-explanatory functions.

### Django
- Use `django-ninja` routers (`Router()`), not `views.py`. Each app defines its own router in `api.py`.
- Routers are mounted in `config/urls.py` on the shared `NinjaAPI` instance.
- Use UUIDs for public-facing primary keys on domain models.
- Use `TextChoices` for enum fields.
- PostgreSQL `SearchVector` for full-text search — no external search engine.
- Database config is parsed from `DATABASE_URL` env var.

### API
- All endpoints live under `/api/`.
- Health check at `GET /api/health`.
- API docs auto-generated at `/api/docs`.
- Auth is stubbed with `X-User-Id` / `X-User-Role` headers for now.

### Celery
- App initialized in `config/celery.py`, autodiscovers tasks from all apps.
- Tasks go in each app's `tasks.py`.
- Hard timeout: 10 min. Soft timeout: 9 min.

### Environment
- All secrets and config via environment variables (see `.env.example`).
- `python-dotenv` loads `.env` in `config/settings.py`.
- Never commit `.env` files.

## Commands

```bash
# Install deps
uv sync

# Run locally (without Docker)
uv run python manage.py runserver
uv run celery -A config worker --loglevel=info

# Run with Docker
docker compose up --build

# Migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Lint
uv run ruff check .
uv run ruff format .

# Tests
uv run python manage.py test
```

## Key Files

| File | Purpose |
|------|---------|
| `config/settings.py` | All Django + Celery + R2 config |
| `config/urls.py` | NinjaAPI instance + router mounting |
| `config/celery.py` | Celery app init |
| `docs/PRD.md` | Product Requirements Document (source of truth for features) |
| `.env.example` | Required environment variables |

## PRD

Read `docs/PRD.md` before implementing any feature. Every model, endpoint, and task must trace back to a defined user flow in the PRD. Do not invent features outside its scope.
