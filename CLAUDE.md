# Backtesting LLM Selector — Webapp de screening (NYSE / NASDAQ)

App de soporte a un proceso de screening de empresas USA/NASDAQ que se analiza
**fuera de la app**. La app **lee** la selección semanal de una base de análisis
externa y la presenta (visor), y permite **backtestear** esas selecciones contra
benchmarks. Estamos en **Fase 4 — Construcción**: de los planos al código real,
**primero backend, después frontend**.

---

## Documentos de planificación — LÉELOS antes de programar

La planificación de las fases 0–3 vive en `docs/`. **Son la fuente de verdad.**
Si el código existente contradice un documento, mandan los documentos (salvo que
se registre y justifique una desviación como ADR, ver más abajo).

- `docs/fase-0-definicion-funcionalidades.md` — qué hace la app, alcance, roles, prioridades día uno.
- `docs/fase-1-decisiones-arquitectura.md` — stack, renderizado, capas, dos BBDD, riesgos asumidos.
- `docs/fase-2-planificacion-v2.md` — dominio (DDD), modelo de datos de la BBDD propia, contratos de API, testing.
- `docs/fase-3-ui-diseno-interfaz-v2.md` — arquitectura de UI, jerarquía de componentes, estados, consumo de API.

**Antes de tocar un área, abre el documento que la gobierna.** Trabajo de
backend → F1 + F2. Trabajo de frontend → F2 (contratos API) + F3.

---

## Reglas de trabajo

1. **Los documentos mandan.** No redecidas lo ya decidido. El etiquetado de los
   docs (`[Heredada]`, `[Diseño nuevo]`, `[Acción F2+]`) indica qué está cerrado
   y qué es trabajo de construcción pendiente.
2. **Las decisiones de construcción se registran como ADR**, no editando los docs
   de fase. Crea un fichero corto en `docs/decisiones/` (ver plantilla
   `ADR-0000-plantilla.md`) y referéncialo en el código/PR. Mantén los docs de
   fase 0–3 como referencia estable.
3. **Si una decisión de construcción contradice o cambia un contrato de F2/F3**,
   NO la apliques unilateralmente: regístrala como ADR con estado "propuesta" y
   adviérteme explícitamente en la respuesta para que yo valide (es el patrón
   "Realimentación F2" de los propios docs).
4. **No introduzcas dependencias nuevas** sin justificarlo en un ADR.
5. **Backend antes que frontend.** No empieces frontend hasta que el contrato de
   API que consume esté implementado o explícitamente fijado.
6. **Tareas bloqueantes primero** (ver más abajo): hay verificaciones contra la
   BBDD real que deben resolverse antes de ciertos módulos.

---

## Stack (de F1, sin desvíos)

- **Frontend:** React como SPA tras login. shadcn/ui (Radix) + Tailwind. recharts para charts. (F1 §4.1, F3 §2)
- **Backend:** FastAPI, orientado a API (sirve JSON, no renderiza HTML). Modelo asíncrono nativo. (F1 §4.2)
- **Dos PostgreSQL separadas** (F1 §4.3):
  - **Análisis** (existente, Railway): esquema legacy ajeno, **solo lectura**, credenciales que impidan escribir. La app NO escribe aquí ni la modela; la consume tras una capa anticorrupción (ACL).
  - **Propia** (nueva): lectura-escritura. Usuarios/roles, backtests persistidos (snapshot completo) y caché de precios/FX. 9 tablas (F2 §5).
- **Repo:** GitHub con ramas `development` / `test` / `production`.
- **Auth:** login con Google (delegada; no se gestionan contraseñas).
- **Integraciones externas:** Google (auth) y **yfinance** (precios + FX), ambas
  encapsuladas tras un puerto mockeable. yfinance es fuente frágil y sustituible.

## Invariantes de negocio que no se negocian (F0/F1/F2)

- **Un único espacio compartido.** El concepto multi-workspace del esqueleto se
  **elimina** (no se simplifica): eliminar workspace y ajustar el alta de usuario
  son el mismo trabajo. (F1 §6)
- **Reporte en USD.** Conversión de divisa por FX del día de cotización. El
  esqueleto asume EUR → ajustar a USD. (F0, F1)
- **Backtest = rotación semanal**, equiponderación **1/N**, contra benchmark
  buy-and-hold. (F0, F2 §1)
- **Backtests inmutables:** sin DELETE, con CANCEL. (F2 §6.5)
- **Snapshot completo:** cada backtest guarda copia autocontenida de lo que usó
  (selecciones, empresas, precios, FX) → reproducible y auditable. (F1 §7.1)
- **`null` ≠ `0`:** los nulos del screening son dato ausente real, nunca cero ni
  vacío. (F2 §6.4, F3)
- **Autorización en el backend**, nunca solo ocultando un botón en el frontend.
  Roles efectivos día uno: `viewer` y `analyst` (crea/cancela backtests); `admin`
  reservado, sin capacidades asignadas día uno. (F1 §5, F2 §5.1)
- **Validación defensiva** al leer la base de análisis: fallar de forma clara y
  diagnosticable si el esquema externo no coincide, nunca producir resultados
  silenciosamente incorrectos. (F1 §7.3, F2 §3)
- **Asincronía estructural:** crear backtest devuelve `202 + pending`; el cliente
  hace polling hasta 
  estado terminal. No hay endpoint que ejecute y espere.
  (F2 §6.5)
- **`Week`** es un Value Object cerrado: lunes 00:00 `America/New_York`. La
  reproducibilidad del snapshot depende de esta convención. (F2 §4.3)

## Tareas BLOQUEANTES de construcción (de F2 §9)

- **Antes de implementar el `WeekResolver`:** verificar en Railway el dominio real
  de `analysis_runs.status` (y `error`/`proceso`/`traceError`) y determinar qué
  valor(es) significan "run terminado OK". Mientras no se verifique, regla
  fail-safe: cualquier `status` no reconocido como OK se trata como NO OK. (F2 §3.1)
- Elegir herramienta de jobs que admita **scheduling nativo** (costura del
  scheduler) y **señal de cancelación**. (F2 §9.7)

## Contratos de API pendientes de cerrar contra F2 (de F3)

Antes de construir el visor, estos contratos de F2 deben cerrarse (las
"Realimentaciones" R1/R2-bis de F3). Si vas a trabajar sobre ellos, avísame:
- **R1:** endpoint de la matriz histórica (empresa × semana).
- **R2-bis:** catálogo de campos de la ficha de empresa.

---

## Comandos

> Rellenar/confirmar al montar el backend. Placeholders:
- Tests: `pytest`
- Lint / formato: `ruff check .` y `ruff format .`
- Arrancar backend (dev): `uvicorn app.main:app --reload`
- Migraciones: `alembic upgrade head`  (confirmar herramienta al decidirla → ADR)

## Estructura del repo

```
.
├── CLAUDE.md                 # este fichero (raíz)
├── backend/                  # FastAPI + dominio (DDD) + adaptadores
├── frontend/                 # React SPA (shadcn/Radix + Tailwind)
└── docs/
    ├── fase-0-definicion-funcionalidades.md
    ├── fase-1-decisiones-arquitectura.md
    ├── fase-2-planificacion-v2.md
    ├── fase-3-ui-diseno-interfaz-v2.md
    └── decisiones/           # ADRs de construcción (fase 4+)
        ├── ADR-0000-plantilla.md
        └── ADR-0001-...
```
