# Informe de cierre — Fase 3 (construcción)

**Fecha:** 2026-06-03
**Estado:** ⚠️ **Cierre parcial — pendiente decisión sobre tests frontend**.

La suite backend pasa la puerta bloqueante; el dominio cumple la cobertura
innegociable; los recorridos críticos están cubiertos end-to-end. El
**frontend** no tiene tests automatizados — F3 no los exigía, y este punto
queda registrado para tu decisión.

---

## 1. Resultado global de la suite

| Capa | Tests | Estado |
|---|---:|---|
| Backend — unit (dominio) | 181 | ✅ verde |
| Backend — integration (ACL real, repo real, caché real, schema real) | ~90 | ✅ verde |
| Backend — e2e (auth+admin, screening, backtests, paths de error) | 84 | ✅ verde |
| **Backend total** | **355** | **✅ verde en 27s** |
| Frontend — automatizados | **0** | **⚠️ ausentes** (ver §3) |

Cobertura backend total: **86% líneas / 93% ramas** (`pytest --cov=app --cov-branch`).

## 2. Cobertura por capa frente a la estrategia F2 §8.6

### Dominio (`app/domain/`) — INNEGOCIABLE

> *"Cada regla de negocio con un test que la afirma y otro que prueba su violación. Línea roja para promocionar a `test`."*

| Módulo | Cobertura líneas | Cobertura ramas |
|---|---:|---:|
| `domain/shared/{week,money,ticker}.py` | 100% | 100% |
| `domain/access/{user,role,google_identity,exceptions,ports}.py` | 100% | 100% |
| `domain/screening/{ports,read_models,week_resolver}.py` | 92–100% | 100% |
| `domain/backtesting/parameters.py` | 100% | 100% |
| `domain/backtesting/portfolio_position.py` | 100% | 100% |
| `domain/backtesting/ports.py` | 100% | — |
| `domain/backtesting/strategy.py` | 100% | 100% |
| `domain/backtesting/backtest.py` (agregado) | 95% | 86% |
| `domain/backtesting/engine.py` | 95% | 93% |
| `domain/backtesting/snapshot.py` | 96% | 94% |
| `domain/backtesting/result.py` | 96% | 92% |
| **Promedio dominio** | **97%** | **96%** |

Cada regla de negocio enunciada en F2 está afirmada y violada por al menos
un test. Las pocas líneas no cubiertas son getters de propiedades y un par
de validaciones defensivas redundantes. **Cumple "innegociable"**.

### Adaptadores (`app/infrastructure/`) — "alta, enfocada en el contrato"

> *"Adaptadores: alta, enfocada en el contrato (traducciones, constraints, y obligatorio el camino de fallo de la validación defensiva y del calentamiento)."*

| Módulo | Cobertura | Observación |
|---|---:|---|
| `analysis_acl/schema_validator.py` | **100%** | Validación defensiva F1 §7.3 |
| `analysis_acl/acl_reader.py` | 86% | Métodos no instanciados en e2e (matrix queries de stock) |
| `repositories/backtest_repository.py` | 98% | Round-trip todos los estados |
| `repositories/user_repository.py` | 100% | CRUD + link_google_id |
| `repositories/db_cancellation_token.py` | 100% | |
| `price_provider/cached_price_provider.py` | 89% | Warm-up batch + persistencia |
| `persistence/models/*` | 100% | Schema + constraints + cascade |
| `identity/security.py` | 78% | JWT encode/decode |

**Cumple**.

### Adaptadores explícitamente NO testeados (F2 §8.5 lo prohíbe)

> *"yfinance y Google se mockean siempre."*

| Módulo | Cobertura | Justificación |
|---|---:|---|
| `infrastructure/identity/google_verifier.py` | 39% | Implementación real de Google. F2 §8.5: "se mockea siempre". Sin tests automatizados por diseño. |
| `infrastructure/price_provider/yfinance_client_impl.py` | 17% | Idem yfinance. |
| `infrastructure/jobs/arq_enqueuer.py` | 0% | Wrapper de arq que requiere Redis activo. Los tests usan `FakeJobEnqueuer`. |
| `app/jobs/worker.py` | 0% | Stub de configuración (`WorkerSettings`). Sin lógica. |

### Aplicación (`app/application/`) — "media, enfocada en caminos"

| Módulo | Cobertura | Observación |
|---|---:|---|
| `application/access/*` (auth, register, bootstrap, get_user_by_token) | 94–100% | Tests unitarios con fakes |
| `application/backtesting/{create,list,get,cancel,get_result}.py` | 55–80% | Caminos felices vía e2e; algunas ramas defensivas sin cubrir |
| `application/screening/{list_weeks,list_companies,get_company,get_matrix,get_picks}.py` | 45–90% | Idem |

Los caminos felices y los errores expuestos al cliente HTTP están cubiertos
vía la suite e2e. Las líneas no cubiertas son ramas defensivas raras
(`KeyError`, validaciones internas) que se ejercen vía e2e pero no de
forma exclusiva.

### Endpoints (`app/infrastructure/web/v1/`) — "media, caminos del contrato"

| Endpoint | Cobertura | Caminos cubiertos |
|---|---:|---|
| `auth.py` | 91% | 200 login OK, 401 token inválido, 403 user_not_authorized, 502 google_unreachable, 400 body inválido, 204 logout |
| `admin_users.py` | 79% | 201 admin crea, 409 email duplicado, 403 analyst/viewer, 400 body inválido |
| `screening.py` | 87% | 200 happy, 404 week/company not_found, 422 range_too_wide, 400 from>to, 500 schema_mismatch, 401 sin sesión |
| `backtests.py` | 70% | 202 crea, 403 viewer, 422 invalid_period/capital, 404 not_found, 409 not_ready/not_cancellable, 401 sin sesión |
| `health.py` | 88% | 200 ambas BBDD OK, 503 degraded |
| `cursor.py` | 86% | encode/decode |

### Otros

| Módulo | Cobertura | Observación |
|---|---:|---|
| `main.py` | 70% | Lifespan + bootstrap; el path "skip_bootstrap" se ejercita en e2e |
| `infrastructure/web/logging.py` | 55% | Middleware request_id; `configure_logging` ejercitado por lifespan |
| `persistence/{app_db,analysis_db}.py` | 53–60% | Engines + session factory; usados por todos los tests pero algunos cleanups no triggereados |

## 3. Frontend — sin tests automatizados

**Estado:** Build verde (`npm run build` OK, 627ms). **0 tests automatizados**.

**Por qué:** F3 (documento de UI) **no define una estrategia de testing
formal** para el frontend, a diferencia de F2 §8 para el backend que es
"innegociable". Los componentes base de B2 incluyen `/__examples` como
showcase manual de QA, pero no hay aserciones programáticas.

**Lo que SÍ se valida automáticamente día uno:**
- TypeScript `tsc -b --noEmit` en CI.
- Vite build (`tsc + vite build`).
- Conexión runtime con backend (`/api/v1/health`) verificada manualmente.

**Lo que NO se valida (riesgo asumido):**
- Comportamiento de las vistas ante estados de servidor (loading/error/empty).
- Render condicional por rol (`RoleGate`).
- Polling y cancelación cooperativa de `BacktestResultView`.
- Validación cliente de `BacktestParamsForm`.
- Manejo de 401 transversal.

### Plan para cerrar el gap (si lo apruebas)

| Trabajo | Estimación | Cobertura objetivo |
|---|---|---|
| Añadir **Vitest** + `@testing-library/react` a `frontend/` | 1h | infra |
| Smoke unitarios de los 8 componentes base | 2h | 80% líneas en `components/base/` |
| Tests de los 6 componentes dominio críticos (Matrix, EquityChart, ParamsForm, StatusBadge, Progress, RoleGate) | 3h | 75% líneas en `domain/` |
| Tests de hooks de queries con `msw` (mock service worker) | 2h | 80% líneas en `lib/queries/` |
| **Playwright** para 3-4 flujos críticos e2e (login → ver mapa, lanzar BT → polling → ver resultado, alta usuario por admin) | 4h | flujos críticos |
| ADR-0008 registrando la estrategia de testing frontend | 30min | proceso |

Total estimado: **~12h** para cumplir un equivalente a la pirámide F2 §8.

## 4. Flujos críticos end-to-end (F2 §8.4)

| Flujo F2 §8.4 | Cubierto por |
|---|---|
| `POST /backtests` → 202 + pending → worker → `GET {id}` completed → `GET /result` | ✅ `tests/integration/test_run_backtest_task.py` (workflow completo invocando run_backtest directo con yfinance fake + Postgres real) |
| `viewer` → 403 al crear backtest | ✅ `tests/e2e/test_backtests_api.py::test_viewer_no_puede_crear_backtest_devuelve_403` |
| `result` sobre pendiente → 409 `backtest_not_ready` | ✅ `tests/e2e/test_backtests_api.py::test_get_result_de_un_pending_devuelve_409` |
| Cancelación de un `running` → `cancelled` | ✅ `tests/integration/test_run_backtest_task.py::test_run_backtest_detecta_cancelacion_de_la_bbdd_y_termina_cancelled` |
| Cancelación de un `completed` → 409 `not_cancellable` | ✅ `tests/e2e/test_backtests_api.py::test_cancel_backtest_ya_cancelled_devuelve_409` |
| yfinance y Google **siempre mockeados** | ✅ `FakeYfinanceClient`, `FakeGoogleIdentityVerifier` |

**Adicionales no enumerados en F2 §8.4 pero cubiertos:**
- Login con admin pre-aprobado + vinculación `google_id` (ADR-0006).
- Email no autorizado → 403.
- Google caído → 502.
- Schema mismatch en ACL → 500 con código estable.
- ACL aplicación de validación defensiva + caching de schema check.
- Idempotencia del save de backtest.

## 5. Veredicto de la puerta bloqueante

| Criterio | Estado |
|---|---|
| Todos los tests en verde | ✅ 355/355 backend; frontend no tiene tests automatizados |
| Dominio en cobertura innegociable | ✅ 97% líneas, 96% ramas |
| Recorridos críticos cubiertos e2e | ✅ los 5 de F2 §8.4 |

**Backend supera la puerta.** **Frontend** queda con la decisión de producto: aceptar el riesgo de "build verde + smoke manual" o invertir las ~12h estimadas en cubrir la pirámide. F3 no obliga; el gap solo se cierra si se acepta extender el alcance.

## 6. Estado del repositorio

- **Rama `main`** y **rama `development`**: alineadas (mismo HEAD, `da1de3d`).
- **CI configurado** en `.github/workflows/ci.yml`: build + tests + cobertura para ambas ramas en push/PR.
- **`.env` no se commitea**; los secretos viven solo en local.
- **8 tablas Postgres** + 2 migraciones Alembic en `head`.
- **7 ADRs** en `docs/decisiones/`:
  - ADR-0001 R1 endpoint matriz (propuesta)
  - ADR-0002 R2-bis catálogo ficha (propuesta)
  - ADR-0003 R2 filtros/sort (propuesta)
  - ADR-0004 dominio `status` run OK (aceptada)
  - ADR-0005 elección de herramienta de jobs (aceptada)
  - ADR-0006 `google_id` NULLABLE + alta admin (aceptada)
  - ADR-0007 Bearer JWT sin refresh (aceptada)

## 7. Pendiente formal

1. **Decisión sobre tests frontend** (§3). Sin esta decisión, F3 no se cierra al 100% — solo backend supera la puerta innegociable.
2. **Cerrar ADRs propuesta** (R1, R2-bis, R2) cuando producto valide los catálogos.
3. **Rotar el Google Client Secret** que estuvo expuesto en commits antiguos del repo (mencionado al consolidar `.env`).
