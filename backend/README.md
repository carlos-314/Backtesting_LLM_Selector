# Backend — Backtesting LLM Selector

Backend en FastAPI orientado a API (F1 §4.2): sirve JSON, no renderiza HTML.
Modelo asíncrono nativo. Dos PostgreSQL separadas — análisis (legacy Railway,
solo lectura) y propia (lectura-escritura). El alcance del backend está
gobernado por los documentos `docs/fase-1-decisiones-arquitectura.md` (F1) y
`docs/fase-2-planificacion-v2.md` (F2). No redecide nada: implementa.

## Requisitos

- **Python 3.11** (`requires-python` en `pyproject.toml`; la elección está
  registrada en memoria de proyecto, no la bajes sin un ADR).
- **Docker + Docker Compose v2** (para Postgres local).
- Acceso a las **credenciales del `.env` raíz** (no en este repo). Ver §
  "Variables de entorno".

## Estructura de carpetas

Separación de capas DDD (F1 §4, F2 §4):

```
backend/
├── app/
│   ├── main.py                 # punto de entrada FastAPI (capa web)
│   ├── config.py               # Settings vía pydantic-settings
│   │
│   ├── domain/                 # núcleo puro: sin imports a FastAPI/Postgres/yfinance
│   │   ├── shared/             # VOs transversales (Week, Money, TickerSymbol)
│   │   ├── screening/          # WeekResolver, read models de Análisis
│   │   └── backtesting/        # agregado Backtest, engine, strategy, puertos
│   │
│   ├── application/            # casos de uso (vacío día uno; se llena al
│   │                           #   construir los endpoints de aplicación)
│   │
│   ├── infrastructure/         # adaptadores: implementan los puertos del dominio
│   │   ├── persistence/        # SQLAlchemy: engines, modelos, sesiones
│   │   │   ├── app_db.py       #   engine BBDD propia (R/W)
│   │   │   ├── analysis_db.py  #   engine BBDD análisis (read-only)
│   │   │   └── models/         #   los 8 modelos de F2 §5
│   │   ├── analysis_acl/       # ACL sobre Railway: SQL crudo + validación defensiva
│   │   ├── price_provider/     # yfinance encapsulado + caché Postgres
│   │   ├── repositories/       # BacktestRepository
│   │   ├── identity/           # JWT/sesión (security.py)
│   │   └── web/                # FastAPI: routers, middlewares, error shape
│   │       ├── errors.py
│   │       ├── logging.py      # middleware request_id (F2 §7.1)
│   │       └── v1/             # /api/v1/* (health día uno; resto al construir)
│   │
│   └── jobs/                   # arq WorkerSettings (ADR-0005)
│
├── alembic/                    # migraciones del schema propio (F2 §5)
│   ├── env.py
│   └── versions/
│
└── tests/
    ├── unit/                   # dominio en aislamiento total (F2 §8.1)
    │   └── domain/
    │       ├── fakes/          # fakes en memoria de los puertos (ciudadanas
    │       │                   #   de primera clase, F2 §8.7)
    │       └── ...
    ├── integration/            # ACL real, repo real, caché real (F2 §8.3)
    └── e2e/                    # API completa con BBDD reales (F2 §8.4)
```

Regla de capa (F1 §4):
- `domain/` no importa de `infrastructure/` ni de `application/`.
- `application/` orquesta dominio + infraestructura; recibe los puertos.
- `infrastructure/` implementa puertos del dominio y conoce frameworks.

## Variables de entorno

El `.env` vive en la **raíz del repo** (un solo archivo, no en `backend/`).
Plantilla mínima:

```ini
# Google OAuth
GOOGLE_CLIENT_ID=<tu_client_id>
VITE_GOOGLE_CLIENT_ID=<mismo_para_frontend>

# JWT
JWT_SECRET=<secreto_de_firma>

# BBDD análisis (Railway, read-only — F1 §4.3)
ANALYSIS_DATABASE_URL=postgresql+asyncpg://app_reader:<pass>@<host>:<port>/railway

# BBDD propia. Si la dejas vacía, fallback automático a la BBDD local Docker.
APP_DATABASE_URL=
```

Notas:
- `ANALYSIS_DATABASE_URL` debe usar **un user con GRANT SELECT únicamente**
  (verificado con `psycopg2` rechazando INSERT/UPDATE/CREATE en ADR-0004).
- `APP_DATABASE_URL` vacío → `postgresql+asyncpg://backtesting:backtesting_dev@localhost:55432/backtesting_app`
  (Postgres del docker-compose).

## Setup local — primera vez

### 1. Levanta Postgres local

```bash
docker compose up -d postgres
```

> Puerto host **55432** (no 5432) para no chocar con un Postgres nativo que
> exista en la máquina. Cambio registrado en `docker-compose.yml`.

### 2. Crea el venv y las dependencias

```bash
# Desde la raíz del repo:
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --upgrade pip
backend/.venv/Scripts/python.exe -m pip install -e backend/[dev]
```

`pyproject.toml` declara las deps; `requirements.txt` es el lock para
reproducibilidad. Tras un `pip install` regenera el lock:

```bash
backend/.venv/Scripts/python.exe -m pip freeze --exclude-editable > backend/requirements.txt
```

### 3. Aplica las migraciones

```bash
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
```

Crea las 8 tablas de F2 §5 en la BBDD propia (local por defecto).

### 4. (Opcional) BBDD de análisis de test

Solo si vas a correr los tests de integración del ACL:

```bash
docker exec backtesting_llm_selector-postgres-1 \
  psql -U backtesting -d postgres -c "CREATE DATABASE backtesting_analysis_test;"
```

Cada test recrea su schema dentro de esa BBDD.

## Arrancar el backend en dev

```bash
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 18000 \
  --app-dir backend
```

> **Puerto 18000 (no 8000).** Windows con Hyper-V/WSL reserva rangos de
> puertos para tunneling (`netsh interface ipv4 show excludedportrange
> protocol=tcp`) y suele incluir el 8000. `uvicorn` falla con
> `error while attempting to bind on address ('127.0.0.1', 8000)`. 18000
> está fuera del rango excluido y el proxy del frontend
> (`frontend/vite.config.ts`) ya apunta ahí.

Endpoints disponibles día uno:
- `GET /api/v1/health` — devuelve `200` con `{status, checks{db_app, db_analysis}}`.

Header `X-Request-ID` se genera/respeta en cada respuesta (F2 §7.1).

## Worker (arq)

ADR-0005: el worker es `arq` con scheduling integrado. Día uno **no hay tareas
registradas** (la tabla `WorkerSettings.functions` está vacía); el stub existe
para que la costura del scheduler quede preparada (F1 §5).

Cuando se añadan tareas (pieza 9 en adelante):

```bash
backend/.venv/Scripts/arq.exe app.jobs.worker.WorkerSettings
```

Requiere Redis (servicio `redis` del docker-compose, aún no levantado por
defecto — `docker compose up -d redis` cuando toque).

## Tests

```bash
# Suite completa (unit + integration + e2e)
backend/.venv/Scripts/python.exe -m pytest backend/tests/

# Solo un nivel
backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/
backend/.venv/Scripts/python.exe -m pytest backend/tests/integration/
backend/.venv/Scripts/python.exe -m pytest backend/tests/e2e/
```

Estrategia: pirámide sesgada al dominio (F2 §8). yfinance y Google se
mockean siempre; Postgres y la base de análisis se prueban contra Postgres
real local.

## Conexiones útiles

| Recurso | DSN |
|---|---|
| BBDD propia local | `postgresql://backtesting:backtesting_dev@localhost:55432/backtesting_app` |
| BBDD análisis test | `postgresql://backtesting:backtesting_dev@localhost:55432/backtesting_analysis_test` |
| BBDD análisis Railway | la del `.env` raíz |

Cliente recomendado: `psql`, DBeaver, o un script Python ad-hoc.

## Migraciones

Crear una nueva migración tras tocar modelos:

```bash
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini revision \
  --autogenerate -m "descripcion_corta"
```

Revisar siempre la migración generada antes de aplicar (autogenerate puede
omitir CHECKs y comentar índices a mano). Aplicar:

```bash
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
```

## Documentación de fase

La fuente de verdad de qué hace el backend está en `docs/` (F0–F3) y en los
ADRs de construcción (`docs/decisiones/ADR-*.md`). El código respeta esos
documentos; cualquier desviación se registra como ADR (ver
`ADR-0000-plantilla.md`).
