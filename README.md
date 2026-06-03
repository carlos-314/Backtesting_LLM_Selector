# Backtesting LLM Selector

Webapp de soporte a un screening de empresas USA/NASDAQ analizadas fuera de la app
y backtests sobre esas selecciones.

- **Backend** — FastAPI + 2× PostgreSQL (análisis legacy en Railway, propia en local).
  Worker arq, validación defensiva (F1 §7.3), 8 tablas (F2 §5).
- **Frontend** — React SPA, shadcn/Radix + Tailwind v4, TanStack Query + Router,
  recharts (F3 ADR M5).

La planificación cerrada (F0–F3) vive en [`docs/`](docs/); las decisiones de
construcción en [`docs/decisiones/`](docs/decisiones/) (ADR-0001…0007).

---

## Levantar el sistema de cero

### 1. Requisitos

- **Python 3.11** (`py -3.11` en Windows debe funcionar).
- **Node 20+** (`npm --version`).
- **Docker + Docker Compose v2** (para Postgres local).
- Acceso al `.env` raíz (no se commitea; contiene los secretos OAuth y la
  URL de la BBDD de análisis Railway). Plantilla:
  ```ini
  GOOGLE_CLIENT_ID=...
  VITE_GOOGLE_CLIENT_ID=...
  JWT_SECRET=...
  ANALYSIS_DATABASE_URL=postgresql+asyncpg://app_reader:PASS@HOST:PORT/railway
  APP_DATABASE_URL=          # vacío → BBDD local Docker
  INITIAL_ADMIN_EMAIL=carlos.picazo.314@gmail.com
  ```

### 2. Postgres local

```bash
docker compose up -d postgres
docker exec backtesting_llm_selector-postgres-1 psql -U backtesting -d postgres \
  -c "CREATE DATABASE backtesting_app;" || true
# BBDDs de test (aisladas del dev — los tests no tocan backtesting_app)
docker exec backtesting_llm_selector-postgres-1 psql -U backtesting -d postgres \
  -c "CREATE DATABASE backtesting_app_test;" || true
docker exec backtesting_llm_selector-postgres-1 psql -U backtesting -d postgres \
  -c "CREATE DATABASE backtesting_analysis_test;" || true
```

> Postgres escucha en el host en **`localhost:55432`** (no `5432`) para no chocar
> con Postgres nativo.

### 3. Backend

```bash
# Crear venv aislado (Python 3.11)
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --upgrade pip
backend/.venv/Scripts/python.exe -m pip install -e backend/[dev]

# Migraciones
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head

# Arrancar API (Windows: usar 18000, no 8000 — Hyper-V port exclusion)
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --reload \
  --port 18000 --app-dir backend
```

Al primer arranque, el lifespan crea el admin inicial (`INITIAL_ADMIN_EMAIL`)
en `app_user` con `role=admin, google_id=NULL`. El primer login vinculará el
`google_id` real (ADR-0006).

Healthcheck: <http://localhost:18000/api/v1/health>.

### 4. Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Abrir <http://localhost:5173>. Login con Google → primer login del admin →
ya estás dentro. Galería de componentes base: <http://localhost:5173/__examples>.

### 5. Worker (cuando haga falta lanzar backtests)

```bash
docker compose up -d redis
backend/.venv/Scripts/arq.exe app.jobs.worker.WorkerSettings
```

### Full stack en Docker (alternativa)

```bash
docker compose up
# → frontend 5173, backend host 18000 / container 8000, postgres 55432, redis 6379
```

---

## Qué quedó construido día uno

| Bloque | Día uno | Estado |
|---|---|---|
| **Visor**: mapa histórico (matriz empresa × semana), ficha de empresa por semana | ✅ | Conectado a backend |
| **Backtests**: lanzar (analyst+admin), polling de estado, cancelar, ver resultado (métricas + equity + drawdown) | ✅ | Asíncrono con arq |
| **Auth**: Google Sign-In + JWT Bearer (ADR-0007) | ✅ | |
| **Alta de usuarios por admin**: POST `/admin/users` (ADR-0006) | ✅ | Endpoint; UI pospuesta |
| **Selección semanal**: lectura vía ACL con validación defensiva | ✅ | F1 §7.3 |
| **Caché yfinance**: warm-up en lote (F2 §4.9) | ✅ | |
| **Snapshot del backtest**: copia congelada (F1 §7.1) | ✅ | |
| **Logging correlacionado**: `X-Request-ID` (F2 §7.1) | ✅ | |
| **CI**: GitHub Actions con build + tests + cobertura | ✅ | `.github/workflows/ci.yml` |

## Qué quedó como costura preparada

| Costura | Estado | Cómo se enchufa |
|---|---|---|
| **Comparar backtests** (`/backtests/comparar`) | Ruta prevista; charts y MetricsPanel ya son N-series | Crear vista que use `useBacktestResultQuery` N veces |
| **Tema oscuro** (F3 §8.1) | Tokens semánticos en `index.css`, `.dark` ya definido | Toggle de clase en `<html>` |
| **Scheduler de precios** (F1 §5) | `arq.WorkerSettings.cron_jobs=[]` listo | Añadir entrada cron + tarea |
| **Pantalla admin de usuarios** (F0/F3 §1.2) | Endpoint POST/GET de `/admin/users` ya construido | Construir vista que consume |
| **Filtros y sort de companies** (ADR-0003 propuesta) | Endpoints sin filtros día uno | Cerrar ADR + implementar query params |
| **Catálogo definitivo de ficha** (ADR-0002 propuesta) | Shape mínimo + raw JSONB | Cerrar ADR + curar campos en backend |
| **Refresh tokens / cookies HTTPOnly** (ADR-0007) | Bearer en memoria día uno | Endpoint `/auth/refresh` + persistencia |
| **Sincronización entre pestañas** (F3 §6.3 C7) | Convergencia por polling | BroadcastChannel cuando convenga |
| **Métricas / observabilidad** (F1 §5) | Logging correlacionado ya emite events | Exporter Prometheus desde logs |

## Informe final de tests y cobertura

Ver [`docs/CIERRE-F3.md`](docs/CIERRE-F3.md).

## Documentación de fase

- [`docs/fase-0-definicion-funcionalidades.md`](docs/fase-0-definicion-funcionalidades.md)
- [`docs/fase-1-decisiones-arquitectura.md`](docs/fase-1-decisiones-arquitectura.md)
- [`docs/fase-2-planificacion-v2.md`](docs/fase-2-planificacion-v2.md)
- [`docs/fase-3-ui-diseno-interfaz-v2.md`](docs/fase-3-ui-diseno-interfaz-v2.md)
- ADRs de construcción: [`docs/decisiones/`](docs/decisiones/)
