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

# Run tests
pip install -r requirements-test.txt
pytest
pytest -v                        # verbose
pytest tests/test_foo.py         # specific file
```

## Architecture

**Stack:** Python 3.13, FastAPI, SQLAlchemy (async), PostgreSQL, Alembic, APScheduler

**Entry point:** [app/main.py](app/main.py) — mounts routers, configures CORS, serves `/media` and `/team_files` static mounts.

**Hidden files (not in git, reconstructed by CI from GitHub secrets):**
- `app/database.py` — SQLAlchemy async engine and session setup (`Base`, `get_db`, `async_session_maker`)
- `alembic.ini` — Alembic database URL

For local development, create `app/database.py` manually (see the file for the template — it reads `DATABASE_URL` from `.env`, defaulting to the Docker Compose PostgreSQL).

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
| `tests/` | pytest test suite |

### Key Domain Concepts

**Series state machine:** `materials_preparation → voice_over → mixing → publication → completed`

**Role states:** `NOT_LOADED → NOT_TIMED → NOT_CHECKED → FIXES_NEED → MIXING_READY`

**Project types:** `off_screen`, `recast`, `dub`

**Deleted user sentinel:** `DELETED_USER_ID = -1` — when a user is deleted, their records in roles/projects are reassigned to this ID rather than cascade-deleted.

## Testing

**Stack:** pytest + pytest-asyncio + httpx + SQLite (aiosqlite) — никакой внешней БД не нужно.

**How it works:**
- `setup_database` (session-scoped) — создаёт все таблицы в `test_redmic.db` перед сессией, удаляет после.
- `client` — `httpx.AsyncClient` с `ASGITransport`; переопределяет `get_db` на тестовую SQLite сессию.
- `auth_headers` — параметризованный фикстур; создаёт пользователя нужного уровня доступа напрямую в БД и возвращает `{"Authorization": "Bearer ..."}`.

**DB cleanliness rules:**
- Tests must leave no traces in the DB — every entity created in a test must be deleted after.
- Helper functions for creating entities (projects, series, roles, etc.) belong in `conftest.py` or dedicated fixture files, not inline in test functions.
- Use `request.addfinalizer` to register cleanup (DELETE) callbacks so entities are removed even if the test fails.

**`auth_headers` usage** (requires `@pytest.mark.parametrize` indirect):
```python
@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_something(client, auth_headers):
    response = await client.get("/users/", headers=auth_headers)
    assert response.status_code == 200
```

Access levels: `1` — участник, `2` — куратор, `3` — администратор, `4` — главный администратор.

### Auth & Permissions

- JWT Bearer tokens, 30-day expiry, bcrypt hashing
- `get_current_user` dependency injected into protected routes
- `AccessChecker` utility for permission validation
- `ProjectChecker` utility for project existence/access

### CORS Origins

- `https://redmic-team.com`
- `https://redmic-workspace-test.ru`
- `http://localhost:35565`

## Code Style

- **Formatting:** black
- **Type hints:** always annotate function parameters and return types
- **FastAPI dependencies:** use `Annotated` syntax per official docs:
  ```python
  from typing import Annotated
  from fastapi import Depends

  async def route(db: Annotated[AsyncSession, Depends(get_db)]):
      ...
  ```

## Deployment

CI/CD via `.github/workflows/deploy.yml`: push to `main` → reconstruct secret files → rsync to server → `alembic upgrade head` → restart systemd service `RM_server`.

Docker Compose runs the API (port 8000) and PostgreSQL 18 (port 5432). Media files persist via named volume `postgres_data` and host-mounted `/media/` and `/team_files/` directories.
