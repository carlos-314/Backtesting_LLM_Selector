# Documento de Planificación — Fase 2: Servidor y Datos

**Producto:** Webapp de soporte a un screening de empresas de bolsa (USA / NASDAQ)
**Fase:** 2 — Servidor y datos (diseño detallado del esqueleto de backend, modelo de datos, contratos de API y estrategia de testing)
**Estado:** Diseño consolidado, revisado tras auditoría de diseño (CTO). No se ha escrito código. Listo como entregable de planificación de la Fase 2.
**Entrada heredada:** Documento de Decisiones de Arquitectura (Fase 1) y esquema de la base de análisis externa (Railway, legacy).
**Historial:** v1 consolidación del diseño; v2 incorpora las correcciones de la auditoría de diseño (ver sección 11).

---

## Cómo leer este documento

Continúa la disciplina de etiquetado de la Fase 1. Cada elemento se marca como una de tres cosas:

- **[Heredada F1]** — decisión de arquitectura o de negocio que viene de la Fase 1 (o antes) y que esta fase respeta sin redecidir.
- **[Diseño nuevo]** — decisión de diseño de servidor/datos tomada en esta fase.
- **[Acción F2+]** — trabajo de ejecución que la construcción (fase posterior) ejecutará; aquí solo queda registrado.

La Fase 2 diseña; **no construye**. Todo lo marcado como acción pertenece a la construcción.

---

## 1. Resolución del gate de entrada

Antes de diseñar nada se cerraron, con negocio, las cuestiones que condicionaban el modelo de dominio y de datos. Resoluciones registradas:

1. **El esquema de la base de análisis es ajeno y de solo lectura.** La puebla un pipeline externo; la app es consumidora. **[Heredada F1]**
2. **Precios y FX vienen de yfinance**, no de la base de análisis (que tiene `lastPrice`, `historicoCotizacion`, `StockPrice` — se ignoran a efectos de mercado). Confirmado explícitamente. **[Heredada F1]**
3. **El grano del screening es semanal.** Cada semana se ejecuta un run de recomendación; si hay dos runs en la misma semana, la semana resuelve al último run OK. **[Heredada F1 (negocio) → regla proyectada en diseño]**
4. **El backtest es una rotación semanal de cartera:** compra los picks entrantes a precio de cierre (close), vende los salientes a precio de apertura (open), compara contra un benchmark buy-and-hold. Es "una estrategia por ahora", no la única posible. **[Heredada F1 (negocio)]**
5. **El periodo del backtest es un parámetro de entrada;** por defecto, todas las semanas disponibles, resueltas en el instante de ejecución. **[Heredada F1 (negocio)]**

### 1.1 Corrección de una hipótesis de partida

Durante el arranque se evaluó un esquema de 16 tablas que resultó **no ser** la base de análisis externa (contenía estado de aplicación: usuarios, workspaces, async_jobs, backtests). Se descartó por completo. La base de análisis real es el esquema legacy de Railway (sección 3). Nada de aquel esquema descartado entra en el diseño.

---

## 2. Tres puntos de tensión heredados, confirmados

Señalados al leer la Fase 1 y confirmados por negocio antes de diseñar:

1. **yfinance como fuente única de precios y FX.** Fuente no oficial y frágil para el núcleo del producto. Se mantiene como decisión cerrada (riesgo asumido F1 §8.1), mitigada con caché día uno y encapsulación tras puerto.
2. **Acoplamiento snapshot ↔ ejecución del backtest.** El snapshot materializa lo que la ejecución leyó; el modelo de datos del snapshot y el flujo de ejecución se diseñan juntos. Tenido presente en todo el diseño.
3. **"Esquema estable" + "validación defensiva".** Se diseña *como si* el esquema externo fuera contrato fijo, y además se valida en runtime por si miente, fallando de forma clara y diagnosticable (F1 §7.3). Postura confirmada.

---

## 3. La base de análisis externa (lectura, no se modela)

Esquema legacy en Railway. La app **solo lee**; no se modela en nuestro lado, se referencia. Entidades relevantes:

| Entidad externa | Qué representa | Uso en la app |
|---|---|---|
| `analysis_runs` (~28) | Cada ejecución del pipeline (`id_run`, `fechaRun`, `run_code`, `status`, `analisis_global`). | Origen del concepto "semana": agrupar por semana desde `fechaRun`, quedarse con el último OK. |
| `processed_stocks` (~41k, 128 col.) | Una fila por `(run × ticker)`: métricas cuantitativas + salidas LLM (JSONB). `UNIQUE(id_run, Ticker)`. | La "empresa analizada" que muestra el screening. |
| `stock` (~11k) | Maestro de tickers (identidad, exchange, divisa). | Identidad del ticker. Sus precios se ignoran (vienen de yfinance). |
| `portfolios` (~228) | Los picks de cada run (`ticker`, `rol`). | La "selección" que alimenta el backtest. |
| `stockDocuments` (~91k) | Documentos crudos por ticker (10-K, transcripts). | No se usa día uno salvo decisión posterior. |
| `stockLastDates` | Vista derivada de `stock`. | No prioritaria. |

**Riesgos de esta base, asumidos:** integridad referencial floja (FKs ausentes en sitios), tipos laxos, columnas duplicadas con distinto casing (`fechaYahooData`/`fechayahoodata2`), CamelCase y mezcla de idiomas (obliga a comillas dobles), campos de control de pipeline mezclados con datos. Todo ello se absorbe en la capa anticorrupción (sección 4).

### 3.1 Dominio de valores externos a verificar antes de construir (auditoría C3)

El `WeekResolver` y la validación defensiva dependen de campos de control externos cuyo dominio de valores **no conocemos a ciencia cierta**: `analysis_runs.status` (declarado `VARCHAR(50) DEFAULT 'STARTED'`), y los campos `error`/`proceso`/`traceError` de `stock`/`processed_stocks`. **Acción de construcción bloqueante:** inspeccionar en Railway los valores reales de `status` y determinar cuál(es) significan "run terminado correctamente" antes de implementar el `WeekResolver`. **[Acción F2+]**

**Regla provisional fail-safe (mientras no se verifique):** cualquier valor de `status` no reconocido explícitamente como "OK" se trata como **no OK** — si no hay certeza de que un run terminó bien, no se muestra ni entra en backtests. Es coherente con F1 §7.3 (no confiar a ciegas en el esquema externo). Tradeoff registrado: posible exclusión de algún run válido si su valor de éxito no estaba en nuestra lista, preferible a incluir un run a medio cocer. **[Diseño nuevo]**

---

## 4. Capa de dominio

### 4.1 Asimetría de fondo

Hay dos naturalezas de dominio conviviendo, y se tratan distinto. El **screening** es ajeno y de solo lectura: no hay invariantes nuestras que proteger, se modela como datos de lectura. El **backtest** es dominio propio de pleno derecho: tiene invariantes y un requisito de reproducibilidad que es el núcleo del producto. DDD se aplica con fuerza en el backtest; en el screening solo como lenguaje ubicuo y frontera de contexto. **[Diseño nuevo]**

### 4.2 Lenguaje ubicuo

| Término | Significado |
|---|---|
| Screening / Semana | El run de análisis de una semana; si hay varios, el último run OK. |
| Empresa analizada | Una fila de `processed_stocks` de un run. |
| Selección / Picks | Los `portfolios` de un run. |
| Backtest | Simulación de rotación de cartera sobre una secuencia de semanas, vs benchmark. |
| Snapshot | Copia autocontenida de todo lo que un backtest usó, que lo hace reproducible. |

### 4.3 Definición operativa de "Semana" (auditoría I1)

`Week` es un Value Object con definición cerrada, no un `DATE` ambiguo. **[Diseño nuevo]**

- **Zona horaria de referencia:** `America/New_York`. Razón: el mercado es USA/NASDAQ; alinear la semana con la sesión bursátil evita que un run nocturno caiga en la "semana equivocada" según la hora de Madrid.
- **Inicio de semana:** lunes 00:00 hora de Nueva York. Una semana es el intervalo [lunes 00:00, lunes siguiente 00:00).
- **Asignación de un run a su semana:** se toma `analysis_runs.fechaRun`, se convierte a `America/New_York`, y se asigna a la semana que contiene ese instante.
- **`week_date` canónica:** la fecha del lunes de esa semana (en NY). Es la clave que se persiste y se expone en la API.

Por qué importa cerrarlo: el `resolved_run_id` congelado en un snapshot depende de esta convención. Si la convención cambiara en el futuro, una semana podría resolver a otro run y romper la reproducibilidad. Fijarla aquí la blinda.

### 4.4 Fronteras de contexto (Bounded Contexts)

Tres contextos. **[Diseño nuevo]**

- **Análisis (Screening)** — upstream, ajeno, solo lectura. Relación: somos downstream y nos protegemos con una **capa anticorrupción (ACL)** que traduce los nombres sucios a lenguaje limpio y aloja la **validación defensiva** (F1 §7.3).
- **Backtesting** — núcleo propio. Agregado `Backtest`, invariantes, estrategia, reproducibilidad. Downstream del Análisis, pero dueño absoluto de su snapshot: una vez ejecutado, no depende de Análisis.
- **Acceso** — identidad y autorización. Usuarios, roles, la capacidad "¿puede lanzar backtests?". Pequeño y transversal.

**Por qué tres y no uno:** mezclar Análisis y Backtesting obligaría a tratar datos ajenos de lectura como entidades nuestras con invariantes, y acoplaría el backtest a cambios del pipeline externo. La separación es lo que permite que el snapshot sea reproducible aunque Análisis cambie debajo.

### 4.5 Responsabilidades que viven en el dominio

Criterio: es dominio si sería verdad aunque cambiáramos de base de datos, framework web o fuente de precios.

**Sí son dominio:** la regla "semana → último run OK"; la definición de `Week`; la mecánica de rotación (entrantes a close, salientes a open, valor de cartera por fecha, benchmark); las invariantes del `Backtest` (periodo válido, secuencia de semanas no vacía, capital > 0, estrategia y benchmark definidos); qué constituye un snapshot reproducible; la regla de autorización.

**No son dominio:** cómo se lee SQL de la base de análisis (acceso a datos); cómo se llama a yfinance y se cachea (acceso a datos / infraestructura); cómo se encola el backtest (aplicación); cómo se valida el JSON de entrada (aplicación).

### 4.6 Entidades, Value Objects y Agregados

**Contexto Análisis — read models planos** (no entidades DDD, no tienen comportamiento que proteger): `Week`, `AnalysisRun`, `AnalyzedCompany`, `Pick`. Los produce la ACL ya traducidos. **[Diseño nuevo]**

**Contexto Backtesting — agregado raíz `Backtest`** (frontera de consistencia). **[Diseño nuevo, protege F1 §7.1]**
- Identidad: `BacktestId`.
- `BacktestParameters` (VO inmutable): periodo de semanas, capital inicial, divisa base, estrategia, benchmark.
- Estado de ciclo de vida: `pending → running → completed | failed | cancelled`, con transiciones como métodos del agregado.
- Resultado (al completar): curva de equity de cartera, métricas, curva de benchmark.
- `ReproducibilitySnapshot` (VO): semanas → run resuelto → picks → precios usados.

VOs de soporte: `Week`, `Money` (importe + divisa), `TickerSymbol`, `PortfolioPosition`.

**Por qué `Backtest` es agregado:** la reproducibilidad es una invariante que cruza parámetros + snapshot + resultado. El agregado garantiza que solo se marca `completed` cuando snapshot y resultado están dentro, coherentes, en la misma operación.

### 4.7 Servicios de dominio

- **`WeekResolver`** — agrupa runs por semana (según la definición de `Week`, 4.3) y aplica "último run OK gana" (con la regla fail-safe de 3.1). Puro. *(La regla vive aquí, no en la ACL: es regla de negocio, no traducción de esquema.)*
- **`BacktestEngine`** — ejecuta la rotación sobre las semanas resueltas con una fuente de precios y produce el resultado. Orquesta estrategia + cálculo de cartera + benchmark. Su flujo de ejecución, incluido el calentamiento de precios, está en 4.9.
- **`RotationStrategy`** (interfaz) — la mecánica "entrantes a close / salientes a open" es *una* implementación. Punto de extensión que recoge el "por ahora" de negocio; no se cablea en el engine.

### 4.8 Aislamiento por puertos (inversión de dependencias)

El dominio **define** las interfaces (puertos) que necesita; las capas externas las implementan. El dominio no importa FastAPI, Postgres ni yfinance. **[Diseño nuevo, implementa la frontera mockeable de F1]**

Puertos definidos por el dominio:
- `AnalysisReadPort` — runs disponibles, picks de un run. Implementa: ACL + acceso a datos.
- `PriceProviderPort` — OHLC de un ticker en una fecha, y FX de un par/fecha; con capacidad de **resolver en lote** (ver 4.9). Implementa: yfinance + caché.
- `BacktestRepositoryPort` — guardar/recuperar un backtest. Implementa: acceso a datos sobre la base propia.

La capa de aplicación recibe el HTTP, valida la entrada, **encola** el trabajo (el backtest no cabe en una petición), y al ejecutar el worker invoca el `BacktestEngine` con las implementaciones concretas. El dominio nunca conoce el worker ni el HTTP. Esto hace el núcleo testeable sin infraestructura (sección 8).

### 4.9 Flujo de ejecución del backtest, con calentamiento de caché (auditoría C2)

El llenado de la caché de precios es un paso **explícito** del flujo, no un efecto colateral disperso. Secuencia que ejecuta el worker: **[Diseño nuevo]**

1. **Resolver semanas:** `WeekResolver` produce la secuencia de semanas del periodo, cada una con su `resolved_run_id` y sus picks.
2. **Calcular necesidades de precios:** a partir de los picks de todas las semanas, el engine determina el conjunto de `(ticker, fecha)` que necesitará (open y close de cada fecha de rebalanceo, FX donde la divisa no sea USD).
3. **Calentamiento (warm-up) de caché en lote:** se pide al `PriceProviderPort` ese conjunto completo *antes* de iniciar la rotación. El puerto lee de `price_cache_daily`/`fx_daily` y descarga de yfinance **solo lo ausente**, en lote, persistiéndolo en caché. Si yfinance falla aquí, el backtest falla limpio (estado `failed` con motivo), sin haber empezado a calcular.
4. **Rotación:** el engine ejecuta la estrategia con los precios ya en memoria/caché. No hay llamadas a yfinance en mitad del cálculo.
5. **Snapshot y resultado:** el engine copia lo usado (semanas, run resuelto, picks, OHLC y FX) al snapshot, calcula métricas y curvas, y el agregado se marca `completed`.

**Por qué así:** concentra el contacto con la fuente frágil (yfinance) en una fase acotada y temprana, evita martillearla en mitad del cálculo, y hace que un fallo de datos sea diagnosticable antes de gastar cómputo. Tradeoff: añade una fase de calentamiento al inicio del job, a cambio de previsibilidad y de proteger la fuente externa.

---

## 5. Modelo de datos

**Solo se modela la base propia de la app.** La de análisis es ajena y ya existe; su "modelo" es el esquema externo, accedido por lectura vía ACL. No hay FK a la base de análisis: es otra base (imposible) e indeseable (acoplaría nuestra integridad a un esquema ajeno y mutable). La integridad referencial entre mundos se sustituye por **copia congelada** en el snapshot. Es la mayor desviación dominio→datos, y es intencionada. **[Diseño nuevo]**

Tipos en PostgreSQL.

### 5.1 Identidad (contexto Acceso)

**`app_user`**

| Columna | Tipo | Clave / regla |
|---|---|---|
| `id` | UUID | PK |
| `email` | TEXT | UNIQUE, NOT NULL |
| `google_id` | TEXT | UNIQUE, NOT NULL — identidad delegada |
| `full_name` | TEXT | NULL permitido |
| `role` | TEXT | NOT NULL, CHECK ∈ {viewer, analyst, admin} |
| `is_active` | BOOLEAN | NOT NULL, default true |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |

**Roles (auditoría I2):** día uno funcionan **dos** capacidades efectivas: `viewer` (lee screening y backtests, no los crea) y `analyst` (además crea y cancela backtests). `admin` se mantiene en el CHECK como **valor reservado** para la futura pantalla de gestión de invitados/roles (aplazada en F1); día uno no otorga ninguna capacidad extra y no debe asignarse. Decisión coherente con el criterio F1 de no arrastrar conceptos muertos: el rol existe en el enum por previsión, pero su semántica se definirá cuando llegue su pantalla. **[Diseño nuevo]**

La capacidad "¿puede lanzar/cancelar backtests?" se **deriva** de `role` (analyst sí, viewer no), no se almacena como booleano (evita estado inconsistente).

### 5.2 Agregado Backtest

**`backtest`** (raíz: parámetros + ciclo de vida)

| Columna | Tipo | Clave / regla |
|---|---|---|
| `id` | UUID | PK |
| `created_by` | UUID | FK → app_user(id), ON DELETE RESTRICT |
| `name` | TEXT | NOT NULL |
| `status` | TEXT | NOT NULL, CHECK ∈ {pending, running, completed, failed, cancelled} |
| `period` | DATERANGE | NOT NULL, CHECK no vacío (inicio ≤ fin en la base) |
| `initial_capital` | NUMERIC(18,2) | NOT NULL, CHECK > 0 |
| `base_currency` | TEXT | NOT NULL, default 'USD' |
| `strategy_code` | TEXT | NOT NULL (hoy: weekly_rotation) |
| `benchmark_code` | TEXT | NOT NULL (hoy: buy_and_hold) |
| `weeks_total` | INT | NULL hasta resolver; nº de semanas del periodo (para progreso) |
| `weeks_processed` | INT | NULL hasta running; semanas ya procesadas (para progreso) |
| `error_detail` | JSONB | NULL salvo `failed`; `{code, message, context}` del fallo |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |
| `started_at` | TIMESTAMPTZ | NULL hasta running |
| `completed_at` | TIMESTAMPTZ | NULL hasta completar/fallar/cancelar |

`ON DELETE RESTRICT` en `created_by` protege la trazabilidad. `DATERANGE` permite el CHECK de periodo en la base. **`base_currency` (auditoría M3):** se mantiene parametrizable por flexibilidad, pero día uno negocio solo usa USD (default); registrado para que el front no exponga otra divisa hasta que se decida. **Progreso y error (auditoría C1):** `weeks_total`/`weeks_processed` dan un progreso honesto (semanas procesadas / total, no un 0-100 inventado, auditoría M1); `error_detail` persiste el motivo del fallo que el contrato expone. El ciclo de job se modela aquí, en el propio agregado, en vez de en una tabla `async_job` separada (ver decisión en 5.6).

**`backtest_result`** (1:1 con backtest, existe solo si `completed`)

| Columna | Tipo | Clave / regla |
|---|---|---|
| `backtest_id` | UUID | PK *y* FK → backtest(id) ON DELETE CASCADE |
| `total_return`, `cagr`, `volatility`, `sharpe`, `max_drawdown` | NUMERIC | métricas núcleo |
| `metrics_extra` | JSONB | métricas adicionales sin tabla rígida |

PK = FK garantiza un único resultado por backtest; que exista esta fila *es* la materialización de "completado".

**Criterio de columna vs `metrics_extra` (auditoría M2):** una métrica va a **columna** si se filtra, ordena o grafica por ella; va a **`metrics_extra`** si es solo informativa. Registrado para evitar que `metrics_extra` se convierta en cajón de sastre. **[Diseño nuevo]**

**`backtest_equity_point`** (serie temporal de cartera y benchmark; append-only, PK BIGINT)

| Columna | Tipo | Clave / regla |
|---|---|---|
| `id` | BIGINT | PK (identity) |
| `backtest_id` | UUID | FK → backtest(id) ON DELETE CASCADE |
| `series` | TEXT | CHECK ∈ {portfolio, benchmark} |
| `point_date` | DATE | NOT NULL |
| `value` | NUMERIC(18,2) | NOT NULL |

Índice UNIQUE `(backtest_id, series, point_date)`. **Desviación del dominio (confirmada):** la "curva de equity" era un VO (lista); en datos se normaliza a filas indexables para graficar rangos por fecha sin deserializar JSON. Se descartó el JSONB con el array entero.

### 5.3 Snapshot de reproducibilidad (F1 §7.1)

**`backtest_snapshot_week`** (una fila por semana del backtest; congela la resolución de la regla)

| Columna | Tipo | Clave / regla |
|---|---|---|
| `id` | UUID | PK |
| `backtest_id` | UUID | FK → backtest(id) ON DELETE CASCADE |
| `week_date` | DATE | NOT NULL — lunes canónico de la semana (NY, ver 4.3) |
| `resolved_run_id` | INTEGER | NOT NULL — el id_run externo que ganó, **copiado, sin FK** |
| `run_code` | TEXT | copia del run_code externo, para auditoría |

UNIQUE `(backtest_id, week_date)`. `resolved_run_id` es la prueba de reproducibilidad: si el pipeline externo añade un run tardío que cambiaría la resolución, este backtest sigue apuntando al que usó.

**`backtest_snapshot_pick`** (picks congelados de cada semana, con OHLC y FX usados)

| Columna | Tipo | Clave / regla |
|---|---|---|
| `id` | UUID | PK |
| `snapshot_week_id` | UUID | FK → backtest_snapshot_week(id) ON DELETE CASCADE |
| `ticker` | TEXT | NOT NULL — símbolo, copiado (no FK) |
| `open`, `high`, `low`, `close` | NUMERIC(18,6) | OHLC usado (completo, por estrategias futuras tipo stops/trailing) |
| `fx_pair` | TEXT | NULL si ya cotiza en USD |
| `fx_rate` | NUMERIC(18,8) | tipo del día de cotización, copiado |

UNIQUE `(snapshot_week_id, ticker)`. Guardar OHLC completo hace el snapshot autocontenido: reconstruirlo no requiere volver a yfinance ni a la caché.

### 5.4 Caché de precios/FX (F1 §7.2)

**`price_cache_daily`** (lo descargado de yfinance, reutilizable; append-heavy, PK BIGINT)

| Columna | Tipo | Clave / regla |
|---|---|---|
| `id` | BIGINT | PK (identity) |
| `ticker` | TEXT | NOT NULL |
| `price_date` | DATE | NOT NULL |
| `open`, `high`, `low`, `close`, `adj_close` | NUMERIC(18,6) | OHLC de yfinance |
| `volume` | BIGINT | NULL permitido |
| `currency` | TEXT | divisa de cotización |
| `source` | TEXT | default 'yfinance' — preparado para multi-fuente futura |
| `fetched_at` | TIMESTAMPTZ | cuándo se descargó |

UNIQUE `(ticker, price_date)` — la clave natural y la "forma mínima" de F1. **`fx_daily`** sigue el mismo patrón con UNIQUE `(pair, date)`.

**Relación caché ↔ snapshot:** la caché alimenta la ejecución, pero el snapshot **copia** el precio usado, no lo referencia ("feeds, no FK"). Son la misma pieza vista dos veces (F1 §7.1), desacopladas para que purgar la caché jamás rompa un backtest pasado. El llenado de la caché lo orquesta el calentamiento del flujo de ejecución (4.9).

### 5.5 Índices previstos por patrón de consulta (auditoría I5)

Más allá de los UNIQUE ya citados, se prevén estos índices, derivados de los accesos reales: **[Diseño nuevo]**

| Índice | Tabla | Motivo (patrón de consulta) |
|---|---|---|
| `(status)` | `backtest` | `GET /backtests?status=...` filtra por estado |
| `(created_by)` | `backtest` | listar backtests por creador |
| `(created_at DESC)` | `backtest` | listado por defecto, orden recencia; base del cursor |
| `(backtest_id, series, point_date)` UNIQUE | `backtest_equity_point` | lectura de la curva por serie ordenada por fecha (el UNIQUE cubre el prefijo) |
| `(backtest_id)` | `backtest_snapshot_week` | recuperar el snapshot de un backtest |
| `(snapshot_week_id)` | `backtest_snapshot_pick` | recuperar picks de cada semana del snapshot |
| `(ticker, price_date)` UNIQUE | `price_cache_daily` | lookup de caché en el calentamiento |

A la escala pequeña y conocida de F1 ninguno es urgente, pero quedan registrados para no descubrir consultas lentas en producción a 5 años.

### 5.6 Desviaciones del dominio y decisiones de modelado, registradas

| Decisión | Dominio decía | Datos hace | Por qué |
|---|---|---|---|
| Sin FK a la base de análisis | "el backtest usa picks de un run" | copia resolved_run_id, ticker, precios | Otra base; FK imposible e indeseable. La copia *es* la reproducibilidad |
| Curva de equity en filas | VO "curva" (lista) | tabla backtest_equity_point | Graficar rangos por fecha sin deserializar; filas indexables |
| backtest_result separado | un solo agregado | dos tablas 1:1 | El resultado existe solo si completed; PK=FK garantiza unicidad |
| Snapshot en dos tablas | un VO ReproducibilitySnapshot | week + pick | Es jerárquico (semanas → picks); dos tablas con CASCADE lo modelan natural |
| role en vez de booleano | "¿puede lanzar backtest?" | columna role + derivación | Evita estado inconsistente; la capacidad se deriva |
| Ciclo de job en `backtest`, no tabla `async_job` aparte | la capa asíncrona de F1 | columnas de progreso/error en la raíz | Día uno solo hay un tipo de job (backtest); meterlo en la raíz es más simple. **Alternativa descartada:** tabla `async_job` genérica — más fiel a F1 y reutilizable para el futuro refresco de precios, pero introduce una tabla y un join sin segundo consumidor todavía. **Costura:** si aparece un segundo tipo de job (scheduler de precios), se extrae entonces a `async_job`. |

---

## 6. Contratos de API (diseño, estilo OpenAPI conceptual)

### 6.1 Reglas transversales

- **Versionado:** prefijo `/api/v1` (por URL, no por header). Cliente único interno; simplicidad sobre content-negotiation. **Alternativa descartada (auditoría M4):** versionado por header `Accept` / content-negotiation — más "puro" y sin ensuciar la URL, pero invisible al depurar y excesivo para un cliente único interno. **[Diseño nuevo]**
- **Autenticación:** todo bajo `/api/v1` exige sesión salvo login y `/health`. Identidad delegada en Google; el backend emite su propia sesión. El transporte de la sesión (cookie httpOnly vs token en cuerpo) queda como **detalle de construcción**, no se fija en el contrato. **[Heredada F1 + Diseño nuevo]**
- **Autorización:** se comprueba en backend, nunca solo ocultando un botón. Capacidad clave: crear/cancelar backtests (analyst). `viewer` lee todo pero no crea ni cancela → 403. **[Heredada F1 + Diseño nuevo]**
- **Forma de error uniforme:** `{ "error": { "code": str, "message": str, "details": obj|null } }`. `code` estable y legible por máquina. **[Diseño nuevo]**
- **Códigos:** 200 OK; 201 creado; **202 aceptado pero aún procesando** (clave para el backtest); 204 sin contenido; 400 mal formado; 401 sin sesión; 403 sin permiso; 404 no existe; 409 conflicto de estado; 422 válido pero inválido por reglas de negocio; 502/503 fallo de dependencia externa; 500 error propio.
- **Fechas y horas (auditoría I6):** todas las fechas/horas en **ISO-8601**; los timestamps en **UTC con offset explícito** (`...Z`); las fechas de calendario (`week_date`, `point_date`) como `YYYY-MM-DD`. La semana sigue la convención de 4.3 (lunes NY) aunque se transmita como fecha simple. **[Diseño nuevo]**
- **Paginación y cursor (auditoría I6, M4):** colecciones que crecen paginan con `limit` (default 50, máx 200) y `cursor`. El **cursor es opaco** y codifica `(created_at, id)` para orden estable ante inserciones. **Alternativa descartada:** `limit`/`offset` — más simple, pero sufre saltos y duplicados si se insertan filas entre páginas; el cursor da orden estable a coste de opacidad. **[Diseño nuevo]**
- **Límites:** rate limiting ligero por sesión (cortafuegos ante bucles del front, no anti-abuso). **[Diseño nuevo]**
- **Asincronismo en el contrato:** crear un backtest **no devuelve el resultado**; devuelve 202 + `pending`. El cliente consulta el estado por **polling** hasta `completed`/`failed`/`cancelled`. SSE/WebSocket queda como costura futura. No hay endpoint que "ejecute y espere". **[Heredada F1 + Diseño nuevo]**

### 6.2 Salud y diagnóstico (auditoría M5)

- **`GET /api/v1/health`** — sin autenticación. Verifica conectividad con ambas BBDD (análisis y propia). `200` → `{ status: "ok", checks: { db_app: "ok", db_analysis: "ok"|"degraded" } }`; `503` si una dependencia crítica está caída. No comprueba yfinance en cada llamada (es bajo demanda); su salud se infiere de los backtests. Valioso en operación a 5 años con dependencias externas frágiles. **[Diseño nuevo]**

### 6.3 Autenticación

- **`POST /api/v1/auth/google`** — intercambia el id_token de Google por sesión propia. Cuerpo `{ google_token: str }`. `200` → `{ user, session.expires_at }`. Errores: `401 invalid_google_token`, `403 user_not_authorized` (email no dado de alta — el alta de invitados está aplazada, día uno = "no estás en la lista"), `502 google_unreachable`.
- **`POST /api/v1/auth/logout`** — invalida la sesión. `204`. `401` si no había sesión.
- **`GET /api/v1/auth/me`** — usuario de la sesión. `200` → `{ user }`. `401` sin sesión.

### 6.4 Screening (lectura vía ACL, read-only)

- **`GET /api/v1/weeks`** — semanas disponibles (ya resueltas a su run ganador). Query: `limit`, `cursor`. `200` → `{ items: [{ week_date, run_code, company_count }], next_cursor }`. Errores: `502 analysis_unreachable`, `500 analysis_schema_mismatch` (cara visible de la validación defensiva F1 §7.3).
- **`GET /api/v1/weeks/{week_date}/companies`** — empresas de esa semana, traducidas por la ACL. Query: `limit`, `cursor`, `sort`, filtros por métrica (a concretar). `200` → `{ week, items: [{ ticker, name, country, currency, metrics{...}, qualitative{...} }], next_cursor }`. Los `null` son explícitos (campos sucios/ausentes en origen). `404 week_not_found`; `502`/`500`.
- **`GET /api/v1/weeks/{week_date}/companies/{ticker}`** — ficha de una empresa. `200` objeto completo (incl. cualitativos LLM). `404 company_not_found`.
- **`GET /api/v1/weeks/{week_date}/picks`** — la selección (portfolios del run). `200` → `{ week, items: [{ ticker, name, role, rank }] }`. `404 week_not_found`.

### 6.5 Backtests (núcleo asíncrono)

- **`POST /api/v1/backtests`** — crea y encola. Requiere capacidad de backtest (analyst). Cuerpo: `name` (oblig.), `period{start,end}` (opcional; null → todas las semanas), `initial_capital` (opcional, >0), `base_currency` (default USD; día uno solo USD), `strategy_code` (default weekly_rotation), `benchmark_code` (default buy_and_hold). `202` → `{ id, status: pending, name, period, created_at, links{self, result, cancel} }`. Errores: `403 backtest_not_permitted` (viewer), `422 invalid_period` (start>end o rango sin semanas — regla de negocio), `422 invalid_capital`, `400` mal formado.
- **`GET /api/v1/backtests`** — lista (espacio compartido). Query: `limit`, `cursor`, `status`. `200` → `{ items:[{id,name,status,created_by,created_at,completed_at}], next_cursor }`.
- **`GET /api/v1/backtests/{id}`** — estado y metadatos. **Endpoint de polling.** `200` → `{ id, status, progress{weeks_processed, weeks_total}|null, name, period, params, created_at, started_at, completed_at, error{code,message}|null }`. El progreso es honesto (semanas, no %). `404 backtest_not_found`.
- **`POST /api/v1/backtests/{id}/cancel`** — solicita cancelar un backtest (auditoría I3). Requiere ser el creador o analyst. `202` → estado pasa a `cancelled` si estaba `pending`/`running`; el worker debe atender la señal de cancelación. `409 not_cancellable` si ya está `completed`/`failed`/`cancelled`. `403`/`404`. **[Diseño nuevo]**
- **`GET /api/v1/backtests/{id}/result`** — resultado completo (solo si completed). `200` → `{ metrics{portfolio,benchmark}, equity_curve{portfolio[],benchmark[]}, snapshot_summary{weeks,first_week,last_week} }`. **`409 backtest_not_ready`** si no está completed (distingue "no existe" de "aún procesa"/"falló"). `404`.
- **`GET /api/v1/backtests/{id}/snapshot`** — snapshot completo congelado (semanas → run → picks con OHLC y FX), para auditoría/reproducibilidad. `200` estructura jerárquica. `409 backtest_not_ready` / `404`.

**Borrado de backtests (auditoría I3):** **no hay DELETE**. Los backtests son **inmutables por auditoría**: validar decisiones de inversión exige que un resultado pasado no se pueda borrar ni alterar (coherente con la reproducibilidad de F1 §7.1). Lo único que se permite sobre un backtest activo es **cancelarlo**. Decisión registrada, no omisión. **[Diseño nuevo]**

### 6.6 Decisiones de contrato, registradas

| Decisión | Porqué | Alternativa descartada |
|---|---|---|
| 202 al crear backtest (no 201) | El recurso no está listo; expresa el asincronismo | 201 + resultado síncrono (imposible: no cabe en la petición) |
| 409 backtest_not_ready ≠ 404 | El cliente en polling distingue "no existe" de "aún procesa" | 404 para ambos (perdería información al cliente) |
| 500 analysis_schema_mismatch propio | Cara visible de la validación defensiva (F1 §7.3) | devolver datos parciales (silenciosamente incorrectos) |
| 422 (reglas negocio) vs 400 (mal formado) | Separa "no entiendo tu JSON" de "pides algo imposible" | un único 400 para todo (menos diagnosticable) |
| Screening read-only | La base de análisis es ajena y de solo lectura | exponer escritura (viola F1) |
| Versionado por URL | Cliente único interno; simplicidad | header/content-negotiation (invisible al depurar) |
| Polling, no SSE | Escala pequeña; SSE como costura futura | SSE/WebSocket día uno (complejidad sin necesidad aún) |
| Backtests inmutables, sin DELETE, con CANCEL | Auditoría/reproducibilidad; pero job largo necesita parada | DELETE libre (rompería la auditoría) |
| Cursor opaco (created_at, id) | Orden estable ante inserciones | limit/offset (saltos/duplicados entre páginas) |

---

## 7. Capas transversales — diseño del día uno (auditoría I4)

F1 marcó varias capas como "día uno". Aquí se **diseñan**, no solo se listan.

### 7.1 Logging estructurado y correlacionado

Logging estructurado (JSON) con un **identificador de correlación** que es el `backtest.id` (y, para peticiones de lectura, un request-id propio). Eventos clave que se loguean con su id: creación de backtest, inicio de job, fin de cada fase del flujo (4.9: resolución, calentamiento, rotación, snapshot), fin con éxito, fallo (con `error_detail`), cancelación, y todo fallo de dependencia externa (yfinance, base de análisis, Google) incluido el `analysis_schema_mismatch`. Concentrado en el trabajo asíncrono y las integraciones, como pidió F1. Las métricas (capa en costura) son derivables de este logging sin reinstrumentar. **[Diseño nuevo, implementa capa día uno de F1]**

### 7.2 Configuración y secretos

Toda credencial **fuera del código y del repositorio**, vía variables de entorno (o gestor de secretos del proveedor). Secretos del día uno: credenciales de la BBDD de análisis (solo lectura), credenciales de la BBDD propia (lectura-escritura), credenciales de cliente OAuth de Google, y cualquier clave/identificación que requiera yfinance. La configuración por entorno (development/test/production) selecciona qué juego de credenciales y qué bases se usan. **[Diseño nuevo, implementa capa día uno de F1]**

### 7.3 Frontera de Google en runtime

Google está tras una frontera mockeable (puerto), igual que yfinance. En runtime, la frontera: valida el `id_token` recibido contra Google, extrae identidad (`google_id`, email), y maneja la indisponibilidad de Google devolviendo `502 google_unreachable` en vez de fallar de forma opaca. Si Google cambiara su API, el impacto queda contenido en esta frontera, no disperso por la app. **[Diseño nuevo, implementa frontera día uno de F1]**

### 7.4 Recordatorio de capas en costura y no aplicables (de F1)

Sin cambios respecto a F1: en **costura preparada** quedan la UI de administración, el scheduler de jobs y las métricas; **no aplican** trazado distribuido, i18n, pagos ni notificaciones.

---

## 8. Estrategia de testing (marco, no tests escritos)

Idea rectora: el valor de un test es proporcional a la regla de negocio que protege e inversamente proporcional al coste de mantenerlo ante cambios irrelevantes. Como la sustancia vive en un núcleo aislado por puertos, se concentra el esfuerzo donde es barato y devastador si falla (dominio).

### 8.1 Niveles y responsabilidad

- **Unitarios (la mayoría):** prueban el dominio en aislamiento total (sin BBDD, sin red, sin FastAPI). `BacktestEngine`, `RotationStrategy`, `WeekResolver` (incluida la definición de `Week` y la regla fail-safe), invariantes del agregado, VOs. Rápidos y deterministas. Son la especificación ejecutable de las reglas de inversión.
- **Integración (los justos, en las costuras):** prueban las adaptaciones a infraestructura contra infraestructura **real** de test. Repositorio sobre Postgres, ACL contra base de análisis de test, caché de precios y su calentamiento.
- **End-to-end (pocos, flujos clave):** un camino completo por la API. Los más caros y frágiles; cubren caminos, no casos.

### 8.2 Aislamiento del dominio

No es una técnica de testing, es consecuencia del diseño: como el dominio define puertos y los recibe como parámetros, probarlo aislado es pasarle implementaciones falsas en memoria. El `BacktestEngine` se prueba con un `PriceProviderPort` falso de precios fijos y semanas predefinidas, verificando que entrante→close, saliente→open, valor por fecha y benchmark son correctos. El `WeekResolver` se prueba con dos runs en la misma semana comprobando que gana el último OK, y con un `status` no reconocido comprobando que aplica el fail-safe. Las invariantes se prueban intentando violarlas (completar sin snapshot → error).

### 8.3 Qué se prueba en integración

- Repositorio sobre Postgres real: guardar un agregado completo y recuperarlo íntegro (snapshot en dos tablas + resultado + estado de job coherentes); mapeo, CASCADE, constraints, índices.
- **ACL contra base de análisis real de test** (el test más valioso): que traduce los casos sucios a read models limpios, y que la **validación defensiva dispara `analysis_schema_mismatch`** cuando el esquema no coincide. Sin este test, F1 §7.3 es solo una intención.
- Caché y su calentamiento: que el warm-up descarga solo lo ausente y reutiliza lo presente; que un fallo de yfinance en el calentamiento deja el backtest `failed` limpio antes de calcular.

### 8.4 Qué se prueba e2e

El flujo estrella: `POST /backtests` → 202 + pending → worker → `GET {id}` completed → `GET /result` métricas coherentes. Caminos de error del contrato: `viewer` → 403; result sobre pendiente → 409; cancelación de un `running` → `cancelled`; cancelación de un `completed` → 409. yfinance y Google siguen mockeados; el resto real.

### 8.5 Mockeo vs real

| Pieza | Unitarios | Integración | E2E |
|---|---|---|---|
| Dominio | real | — | real |
| PriceProviderPort (yfinance) | mock | mock | mock |
| AnalysisReadPort / ACL | mock | **real** (base de test) | real |
| BacktestRepositoryPort (Postgres) | mock en memoria | **real** | real |
| Cola + worker | — | — | **real** |
| Google auth | mock | mock | mock |

Principio: **yfinance y Google se mockean siempre** (fronteras externas frágiles; por eso F1 las puso tras puertos). **Postgres y la base de análisis se prueban reales** en integración: su valor está en el detalle que un mock no captura (constraints, CASCADE, tipos sucios).

### 8.6 Cobertura

No se persigue un porcentaje global. Por capa:
- **Dominio: innegociable.** Cada regla de negocio con un test que la afirma y otro que prueba su violación. Línea roja para promocionar a `test`.
- **Adaptadores: alta, enfocada en el contrato** (traducciones, constraints, y obligatorio el camino de fallo de la validación defensiva y del calentamiento).
- **Endpoints/aplicación: media, enfocada en caminos** (códigos 202/403/409/422, flujo asíncrono, cancelación).
- **Glue trivial (DTOs, serialización): baja, sin remordimiento.**

### 8.7 Organización y nomenclatura

```
tests/
  unit/
    domain/
      test_backtest_engine.py
      test_rotation_strategy.py
      test_week_resolver.py
      test_week_value_object.py
      test_backtest_aggregate.py
      test_value_objects.py
    fakes/
      fake_price_provider.py
      fake_analysis_reader.py
      in_memory_backtest_repo.py
  integration/
    test_backtest_repository.py
    test_analysis_acl.py
    test_price_cache_warmup.py
  e2e/
    test_backtest_lifecycle.py
    test_backtest_cancellation.py
    test_authorization_gates.py
  conftest.py
```

Convención: `test_<unidad>_<condición>_<resultado>`. Ej.: `test_engine_entrante_se_compra_a_close`, `test_resolver_dos_runs_misma_semana_gana_ultimo`, `test_resolver_status_desconocido_se_trata_como_no_ok`, `test_result_endpoint_backtest_pendiente_devuelve_409`. El nombre debe leerse como la regla que afirma. Las `fakes/` son ciudadanas de primera clase: las implementaciones en memoria de los puertos, prueba de que el aislamiento funcionó.

### 8.8 Tradeoffs registrados

| Decisión | Tradeoff asumido |
|---|---|
| Pirámide sesgada a la base | Los unitarios no detectan fallos de integración (los cubren las otras capas) |
| ACL contra base real en integración | Tests lentos, base de test que mantener; se acepta por cubrir F1 §7.3 |
| yfinance/Google siempre mockeados | No se prueba la integración real en CI; se cubre con test de humo manual aparte |
| Pocos e2e | Cobertura e2e incompleta a propósito; lo raro se cubre en capas inferiores |
| Cobertura por capa, no global | Requiere criterio humano en revisión, no un número |
| Postgres real en integración | Necesita base de test en CI (contenedor) |
| Base de análisis de test = subconjunto curado a mano | Más control sobre los casos sucios deliberados, menos "realismo" que copia de Railway |

---

## 9. Trabajo de construcción registrado (Acciones F2+)

1. Implementar el esqueleto FastAPI orientado a API con la frontera SPA↔API. **[Acción]**
2. Implementar las dos conexiones PostgreSQL (análisis solo-lectura con credenciales que impidan escribir; propia lectura-escritura). **[Acción, de F1]**
3. **Verificar en Railway el dominio de valores de `analysis_runs.status`** (y `error`/`proceso`) antes de implementar el `WeekResolver`; aplicar la regla fail-safe de 3.1. **[Acción, bloqueante]**
4. Construir la ACL sobre la base de análisis, con traducción de nombres y validación defensiva (punto e implementación de F1 §7.3). **[Acción]**
5. Implementar el `Week` con la definición operativa de 4.3 (lunes NY). **[Acción]**
6. Encapsular yfinance y Google tras sus puertos mockeables; implementar el calentamiento de caché en lote (4.9). **[Acción]**
7. Elegir herramienta de jobs que admita scheduling nativo (costura del scheduler — criterio de F1) y soporte señal de cancelación. **[Acción, de F1]**
8. Implementar el modelo de datos de la sección 5 (migraciones de la base propia), con los índices de 5.5. **[Acción]**
9. Resolver EUR→USD del esqueleto (alcance incierto hasta abrir el código). **[Acción, de F1]**
10. Eliminar el concepto multi-workspace del esqueleto y ajustar el alta de usuario (mismo trabajo). **[Acción, de F1]**
11. Implementar el logging correlacionado (7.1), la gestión de secretos (7.2) y la frontera de Google en runtime (7.3). **[Acción]**
12. Implementar `GET /health` (6.2) y `POST /backtests/{id}/cancel` con atención de la señal en el worker. **[Acción]**
13. Construir la suite de tests según el marco de la sección 8, empezando por el dominio. **[Acción]**

---

## 10. Riesgos asumidos (heredados de F1, vigentes)

1. Fuente de datos de mercado única y frágil (yfinance) — mitigada con caché día uno, calentamiento en lote acotado (4.9), encapsulación tras puerto, tolerancia a fallo.
2. Esquema de análisis externo sin contrato verificable — cubierto con validación defensiva, su código de error propio, la regla fail-safe de 3.1 y la verificación bloqueante de valores (acción 3).
3. Sin datos de equipo/presupuesto — decisiones sesgadas a lo operativamente barato y mantenible por una persona.
4. Coste de refactorización del workspace — se asume a cambio de no heredar deuda conceptual.

---

## 11. Cambios incorporados tras la auditoría de diseño (CTO)

Resumen de qué resolvió la auditoría, para trazabilidad:

- **C1** — ciclo de job modelado: `weeks_total`/`weeks_processed`/`error_detail` en `backtest` (5.2); progreso honesto por semanas (M1).
- **C2** — calentamiento de caché diseñado como fase explícita del flujo (4.9).
- **C3** — verificación bloqueante del dominio de `status` + regla fail-safe (3.1, acción 3).
- **I1** — `Week` con definición operativa cerrada (lunes NY) (4.3).
- **I2** — roles resueltos: viewer/analyst efectivos, admin reservado (5.1).
- **I3** — borrado/cancelación: inmutables sin DELETE, con CANCEL (6.5).
- **I4** — capas día uno diseñadas: logging, secretos, frontera Google (sección 7).
- **I5** — índices por patrón de consulta (5.5).
- **I6** — fechas ISO/UTC y cursor opaco definidos (6.1).
- **M2** — criterio columna vs metrics_extra (5.2).
- **M3** — base_currency parametrizable, día uno USD (5.2).
- **M4** — alternativas descartadas añadidas a versionado y cursor (6.1, 6.6).
- **M5** — `GET /health` (6.2).

---

## 12. Resumen ejecutivo

- **Dominio:** tres bounded contexts (Análisis ajeno de lectura / Backtesting propio rico / Acceso). Agregado `Backtest` que protege la reproducibilidad como invariante. `Week` con definición operativa cerrada. Aislamiento por puertos; el núcleo no conoce FastAPI, Postgres ni yfinance. Flujo de ejecución con calentamiento de caché explícito.
- **Datos:** solo se modela la base propia (9 tablas). Ninguna FK a la base de análisis; integridad entre mundos por copia congelada en el snapshot. Ciclo de job (progreso/error) en la raíz `backtest`. Índices previstos por patrón de consulta.
- **API:** `/api/v1`, sesión tras Google, autorización en backend. Screening read-only. Backtest asíncrono en el contrato (202 + polling + 409), con cancelación e inmutabilidad por auditoría. Fechas ISO/UTC, cursor opaco. `/health` para operación.
- **Capas transversales día uno:** logging correlacionado, secretos fuera del código, frontera de Google en runtime — diseñadas, no solo listadas.
- **Testing:** pirámide sesgada al dominio (innegociable), integración real en las costuras (Postgres y ACL + calentamiento), e2e mínimo sobre flujos clave incluida la cancelación. yfinance/Google siempre mockeados.
- **Esqueleto:** se respeta React/FastAPI/Google/yfinance; se ajusta EUR→USD, una→dos BBDD y la encapsulación de yfinance; se elimina la multi-workspace.

La Fase 2 (diseño), revisada tras auditoría, queda consolidada. El siguiente paso del proceso es la **construcción**: de los planos al código real, primero backend y después frontend, con tests según el marco de la sección 8.
