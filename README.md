# RedMicWS

Backend-сервис для управления командой русского дубляжа/озвучки. FastAPI-приложение с PostgreSQL, SQLAlchemy (async) и Alembic.

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-blue.svg)](https://www.postgresql.org/)

---

## Оглавление

- [О проекте](#о-проекте)
- [Стек технологий](#стек-технологий)
- [Быстрый старт](#быстрый-старт)
- [Структура проекта](#структура-проекта)
- [Модули](#модули)
- [API Reference](#api-reference)
- [Система ролей и прав](#система-ролей-и-прав)
- [State Machine](#state-machine)
- [Тестирование](#тестирование)
- [Миграции](#миграции)
- [Деплой](#деплой)

---

## О проекте

RedMicWS — REST API для управления процессом озвучки сериалов/аниме. Позволяет:

- Управлять проектами дубляжа и их участниками
- Создавать серии (эпизоды) и назначать команду (режиссёр, таймер, звукорежиссёр и т.д.)
- Загружать ASS-субтитры, автоматически парсить роли и создавать SRT-файлы
- Управлять ролями актёров: записи, фиксы, проверка, тайминг
- Отслеживать прогресс озвучки каждой серии
- Управлять командой: уровни доступа, периоды отдыха, контакты

---

## Стек технологий

| Категория | Технология |
|---|---|
| **Framework** | FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Database** | PostgreSQL 18 |
| **Migrations** | Alembic |
| **Auth** | JWT (PyJWT) + bcrypt (passlib) |
| **Scheduler** | APScheduler (cron для управления периодами отдыха) |
| **Parsing** | pysubs2 (ASS/SSA субтитры) |
| **Validation** | Pydantic v2 |
| **Tests** | pytest + pytest-asyncio + httpx + aiosqlite |
| **Dev** | Docker Compose, Uvicorn |

---

## Быстрый старт

### Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker-compose up --build
```

API будет доступен на `http://localhost:8000`, Swagger-документация — `http://localhost:8000/docs`.

### Миграции

```bash
alembic upgrade head          # Применить все миграции
alembic revision --autogenerate -m "description"  # Создать новую миграцию
```

---

## Структура проекта

```
app/
├── main.py                 # Точка входа, CORS, статические файлы, lifespan
├── database.py             # Async SQLAlchemy engine, session, Base
├── users/                  # Пользователи, аутентификация, контакты
├── projects/               # Проекты дубляжа, участники, роли проекта
├── series/                 # Серии/эпизоды, субтитры, материалы
├── roles/                  # Роли актёров, записи, фиксы
├── levels/                 # Уровни команды (director, translator и т.д.)
├── files/                  # Загрузка и хранение файлов
├── links/                  # Универсальные ссылки
├── migrations/             # Alembic миграции
└── tests/                  # pytest тесты
```

Каждый модуль следует единому паттерну:

| Файл | Назначение |
|---|---|
| `models.py` | SQLAlchemy ORM модели |
| `schemas.py` | Pydantic схемы запросов/ответов |
| `routes.py` | FastAPI эндпоинты (APIRouter) |
| `utils.py` | Утилиты, чекеры доступа, хелперы |

---

## Модули

### Users

Аутентификация, профили, контакты, периоды отдыха.

- JWT Bearer токены (30 дней, HS256)
- bcrypt хеширование паролей
- APScheduler cron-задача (полночь) — автоматическое управление `is_active` по датам отдыха

### Projects

Управление проектами дубляжа.

- Типы: `закадр`, `рекаст`, `дубляж`
- Статусы: `подготовка`, `в работе`, `завершён`, `приостановлен`, `закрыт`
- Участники, кураторы, ссылки, роли проекта

### Series

Серии (эпизоды) внутри проектов.

- ASS-парсинг субтитров (по Name или Style)
- Автоматическое создание ролей и SRT-файлов
- Материалы, ссылки, фиксы субтитров
- Назначение команды: куратор, звукорежиссёр, таймер, переводчик, режиссёр

### Roles

Роли актёров в сериях.

- Загрузка записей (wav, flac, mp3)
- CRUD фиксов (phrase + note + ready)
- Обновление SRT-файлов
- Автоматический расчёт состояния роли

### Levels

Уровни команды (многие-ко-многим с User).

- Soft delete (`is_active=False`)
- Определяют максимальный уровень доступа пользователя

### Files

Загрузка файлов в `team_files/` с UUID-именами.

### Links

Глобальные ссылки с категоризацией.

---

## API Reference

### Статические файлы

| Путь | Назначение |
|---|---|
| `/media` | Аватарки, демо, обложки проектов |
| `/team_files` | Загруженные файлы команды |
| `/subs` | ASS и SRT субтитры |
| `/records` | Аудиозаписи ролей |

### Ключевые эндпоинты

#### Users — `/users`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/` | Список пользователей | Auth |
| `GET` | `/{user_id}` | Детали пользователя | Auth |
| `POST` | `/` | Создание пользователя | Admin 3+ |
| `POST` | `/login` | Аутентификация | Public |
| `PATCH` | `/{user_id}` | Обновление профиля | Owner / Admin 3+ |
| `DELETE` | `/{user_id}` | Удаление пользователя | Senior Admin 4+ |
| `POST` | `/{user_id}/level` | Назначение ролей | Curator 2+ |
| `PUT` | `/{user_id}/avatar` | Загрузка аватарки | Owner / Admin 3+ |
| `POST` | `/{user_id}/rest` | Установка периода отдыха | Owner / Curator 2+ |

#### Projects — `/projects`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/` | Список проектов | Auth |
| `GET` | `/{project_id}` | Детали проекта | Auth |
| `POST` | `/` | Создание проекта | Curator 2+ |
| `PATCH` | `/{project_id}/title` | Обновление названия | Curator 2+ / Curator проекта |
| `PUT` | `/{project_id}/status` | Обновление статуса | Curator 2+ / Curator проекта |
| `POST` | `/{project_id}/participants` | Добавить участника | Curator 2+ / Curator проекта |
| `DELETE` | `/{project_id}` | Удаление проекта | Curator 2+ / Curator проекта |

#### Series — `/series`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/user/{user_id}/work` | Работа пользователя | Auth |
| `GET` | `/` | Список серий | Auth |
| `GET` | `/{series_id}` | Детали серии | Auth |
| `POST` | `/{project_id}` | Создание серии | Curator 2+ |
| `PATCH` | `/{seria_id}/noactors` | Назначение команды | Curator 2+ / Curator серии |
| `PATCH` | `/{seria_id}/data` | Обновление метаданных | Curator 2+ / Staff серии |
| `PUT` | `/{seria_id}/subs` | Загрузка ASS-файла | Curator 2+ / Participant |
| `POST` | `/{seria_id}/role` | Создание роли | Curator 2+ / Curator серии |
| `PUT` | `/role/{role_id}/actor` | Назначение актёра | Director / Curator 2+ |
| `PATCH` | `/role/{role_id}/state` | Обновление checked/timed | Curator 2+ / Staff серии |
| `PUT` | `/role/{role_id}/subtitle` | Загрузка SRT | Curator 2+ / Staff серии |
| `POST` | `/role/{role_id}/records` | Загрузка записи | Curator 2+ / Actor роли |
| `POST` | `/role/{role_id}/fixs` | Создание фикса | Curator 2+ / Staff серии |
| `PATCH` | `/role/fixs/{fix_id}` | Отметить фикс готовым | Curator 2+ / Staff серии |
| `DELETE` | `/{seria_id}` | Удаление серии | Curator 2+ / Curator проекта |

---

## Система ролей и прав

### Уровни доступа

| Уровень | Название | Возможности |
|---|---|---|
| 1 | Участник | Базовый доступ к своим сериям и ролям |
| 2 | Куратор | Создание проектов/серий, управление участниками |
| 3 | Администратор | Создание пользователей, загрузка файлов |
| 4 | Главный администратор | Удаление пользователей, управление ролями |

### Механизм проверки

- `get_max_lvl(db, user)` — возвращает максимальный `access_level` пользователя
- `LevelChecker(min_level)` — dependency-инжектор для проверки минимального уровня
- `AccessChecker` — проверка: уровень 2+ ИЛИ пользователь является куратором проекта
- Специализированные чекеры для каждого эндпоинта серии (`SeriesDataAccessChecker`, `SubsAccessChecker`, `SeriesRoleRecordAccessChecker` и др.)

---

## State Machine

### Состояния серии (SeriesState)

```
подготовка материалов → озвучка → сведение → проверка → публикация → завершено
```

### Состояния роли (RoleState)

```
не загружена → не затаймлена → не проверена → требуются фиксы → готова к сведению
```

Переходы управляются автоматически:
- Загрузка записи → сброс `timed` и `checked` → `не загружена`
- Обновление `checked`/`timed` → пересчёт через `compute_role_state()`
- Наличие неготовых фиксов → `требуются фиксы`

### Прогресс озвучки (dub_progress)

| Значение | Условие |
|---|---|
| `no_roles` | Роли ещё не созданы |
| `on_rest` | Кто-то из актёров в периоде отдыха |
| `finished` | Все роли завершены (checked + timed + нет фиксов + есть записи) |
| `on_process` | Роли в процессе работы |

---

## Тестирование

```bash
pip install -r requirements-test.txt
pytest
pytest -v                        # verbose
pytest tests/test_series.py      # конкретный файл
```

**Особенности:**
- SQLite + aiosqlite — никакой внешней БД не требуется
- Параметризованный фикстура `auth_headers` для проверки доступа
- Автоматическая очистка через `request.addfinalizer`
- Хелперы для создания сущностей в `tests/helpers/`

### Пример теста с авторизацией

```python
@pytest.mark.parametrize("auth_headers", [{"level": 2}], indirect=True)
async def test_get_series(client, auth_headers):
    response = await client.get("/series/", headers=auth_headers)
    assert response.status_code == 200
```

---

## Миграции

```bash
# Применить все миграции
alembic upgrade head

# Создать новую миграцию
alembic revision --autogenerate -m "add column to table"

# Откатить на одну миграцию
alembic downgrade -1

# Проверить текущую версию
alembic current
```

---

## Деплой

CI/CD через `.github/workflows/deploy.yml`:

1. Push в `main`
2. Восстановление секретных файлов (`database.py`, `alembic.ini`)
3. Rsync на сервер
4. `alembic upgrade head`
5. Restart systemd service `RM_server`

### CORS

Разрешённые origins:
- `https://redmic-team.com`
- `https://redmic-workspace-test.ru`
- `http://localhost:35565`

---

## Code Style

- **Форматирование:** Black
- **Type hints:** Аннотации параметров и возвращаемых типов
- **FastAPI зависимости:** `Annotated` + `Depends`
- **Модели:** `Mapped[...]` + `mapped_column` (SQLAlchemy 2.0 style)