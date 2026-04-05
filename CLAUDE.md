# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RedMicWS is a FastAPI backend for a Russian dubbing/voice-over team workspace. It manages projects, series (episodes), voice actor roles, recordings, and team members.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker (preferred for local dev with database)
docker-compose up --build

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

There is no test suite currently.

## Architecture

**Stack:** Python 3.13, FastAPI, SQLAlchemy (async), PostgreSQL, Alembic, APScheduler

**Entry point:** [app/main.py](app/main.py) — mounts routers, configures CORS, serves `/media` and `/team_files` static mounts.

**Hidden files (not in git, reconstructed by CI from GitHub secrets):**
- `app/database.py` — SQLAlchemy async engine and session setup
- `alembic.ini` — Alembic database URL

### Module Structure

Each module under `app/` follows the same pattern: `models.py` (SQLAlchemy ORM), `schemas.py` (Pydantic), `router.py` (FastAPI endpoints), `utils.py` (helpers).

| Module | Purpose |
|---|---|
| `users/` | Authentication (JWT/bcrypt), user profiles, contacts |
| `projects/` | Dubbing projects, participant management |
| `series/` | Episodes within projects, state machine |
| `roles/` | Voice actor roles, recordings, fix tracking |
| `levels/` | Team hierarchy definitions (director, translator, etc.) |
| `files/` | File upload metadata tracking |
| `links/` | Generic URL links attached to projects/series |
| `migrations/` | Alembic migration versions |

### Key Domain Concepts

**Series state machine:** `materials_preparation → voice_over → mixing → publication → completed`

**Role states:** `NOT_LOADED → NOT_TIMED → NOT_CHECKED → FIXES_NEED → MIXING_READY`

**Project types:** `off_screen`, `recast`, `dub`

**Deleted user sentinel:** `DELETED_USER_ID = -1` — when a user is deleted, their records in roles/projects are reassigned to this ID rather than cascade-deleted.

### Auth & Permissions

- JWT Bearer tokens, 30-day expiry, bcrypt hashing
- `get_current_user` dependency injected into protected routes
- `AccessChecker` utility for permission validation
- `ProjectChecker` utility for project existence/access

### CORS Origins

- `https://redmic-team.com`
- `https://redmic-workspace-test.ru`
- `http://localhost:35565`

## Deployment

CI/CD via `.github/workflows/deploy.yml`: push to `main` → reconstruct secret files → rsync to server → `alembic upgrade head` → restart systemd service `RM_server`.

Docker Compose runs the API (port 8000) and PostgreSQL 18 (port 5432). Media files persist via named volume `postgres_data` and host-mounted `/media/` and `/team_files/` directories.
