# ADR-0005 — Elección de herramienta de jobs (cola + worker)

**Fecha:** 2026-06-03
**Estado:** aceptada
**Toca contrato de fase previa:** No (resuelve la **acción bloqueante F1 §5 / F2 §9.7 / CLAUDE.md tareas bloqueantes** — elegir herramienta de jobs antes de codear el worker)

## Contexto

F1 §5 marca **cola + worker** como capa "día uno" (asincronía estructural por la
naturaleza del trabajo, no por escala) y **scheduler** como **costura preparada**
sobre la misma infraestructura. F1 §9.5 traslada a F2 el criterio operativo:

> *"Elegir herramienta de jobs que admita scheduling nativo (para que la costura
> del scheduler quede preparada)."*

F2 §9.7 lo refina:

> *"Elegir herramienta de jobs que admita scheduling nativo (costura del scheduler)
> y soporte señal de cancelación."*

F2 §6.5 lo cementa en el contrato: `POST /backtests/{id}/cancel` requiere que el
worker **atienda** la señal en mitad de la rotación (no es una bandera cosmética).

## Criterios de elección (derivados de F1+F2)

| # | Criterio | Origen |
|---|---|---|
| 1 | **Scheduling nativo** (cron) integrado en el worker, no librería aparte | F1 §5, F2 §9.7 |
| 2 | **Señal de cancelación** atendible mid-job | F2 §6.5, §9.7 |
| 3 | Encaja con **FastAPI async**: el endpoint enqueña sin bloquear, devuelve 202 | F2 §6.5 |
| 4 | Worker **mockeable** y testeable contra cola real | F2 §8.4 (e2e con cola real) |
| 5 | Operable por **una sola persona** (F1 §8.3) → simplicidad operativa | F1 §8.3 |
| 6 | **Broker mínimo**: Redis ya es candidato natural (esqueleto y compose lo traen); evitar exigir RabbitMQ | esqueleto + F1 §6 |
| 7 | Mantenida activamente (proyecto a 5 años) | F1 §8.3 |
| 8 | Sin licencia comercial | criterio implícito |

## Candidatas evaluadas

### Celery
- **Licencia/coste:** BSD-3, sin coste.
- **(1) Scheduling:** sí, integrado (`celery-beat`). Proceso separado pero del mismo
  proyecto, configurado en el mismo código.
- **(2) Cancelación:** `app.control.revoke(task_id, terminate=True)` — envía SIGTERM
  al worker que ejecuta la tarea. Para una rotación que itera semanas, hay que
  programar la atención con `signal.signal(...)` o consultando `task.is_aborted()`
  en cada iteración. Posible, no idiomático.
- **(3) FastAPI async:** Celery es **sync-first**. Llamar a `task.delay()` desde
  endpoint async funciona, pero el worker ejecuta en hilo bloqueante; el código
  del worker no es async nativo (hay `celery[asyncio]` experimental, no estable).
- **(4) Mockeable:** sí, `task_always_eager=True` para tests; e2e real con Redis.
- **(5) Operable:** dos procesos (worker + beat), configuración densa. Cada
  upgrade mayor exige cuidado (Celery 5 vs 6 tuvo breaking changes notables).
- **(6) Broker:** Redis o RabbitMQ. Compatible.
- **(7) Mantenimiento:** muy maduro, ecosistema enorme, pero ralentizado (releases
  espaciados; el autor abandonó hace años, comunidad lo sostiene).
- **Veredicto:** cumple todos los criterios pero su modelo sync no encaja con
  FastAPI async; el "código del worker" sería una rama paralela del estilo del
  resto del backend.

### arq
- **Licencia/coste:** MIT, sin coste.
- **(1) Scheduling:** sí, integrado. `cron(...)` como decorador o en `WorkerSettings`,
  ejecutado por el mismo worker (sin proceso `beat` separado).
- **(2) Cancelación:** `await job.abort(timeout=...)` — el worker comprueba
  cooperativamente. Para atenderlo mid-rotación basta con consultar el flag
  en cada iteración de semana (idiomático).
- **(3) FastAPI async:** **nativo**. Tareas son `async def`, worker corre sobre
  `asyncio`. Encaja con la naturaleza async del backend de F1 §4.2.
- **(4) Mockeable:** sí, contexto de test ofrecido; e2e real con Redis.
- **(5) Operable:** un solo proceso (`arq worker.WorkerSettings`). Configuración
  mínima (un módulo).
- **(6) Broker:** **Redis exclusivamente**. Coincide con el esqueleto.
- **(7) Mantenimiento:** mantenido por Samuel Colvin (autor de Pydantic, FastAPI
  Tiangolo lo recomienda). Releases regulares. Comunidad menor que Celery pero
  vigente.
- **Veredicto:** cumple todos los criterios y encaja idiomáticamente con FastAPI.

### Dramatiq
- **Licencia/coste:** LGPL-3, sin coste. Add-on comercial opcional (Dramatiq Plus)
  no necesario.
- **(1) Scheduling:** **no nativo en core**. Requiere `dramatiq-periodiq` o
  `apscheduler` adjunto. Esto incumple el criterio 1 (la "costura preparada" de
  F1 §5 deja de quedar "gratis", al exigir otra pieza).
- **(2) Cancelación:** se gestiona vía middleware o flags en `Message.options`;
  posible pero menos directo que arq.
- **(3) FastAPI async:** **sync-first**. Similar a Celery.
- **(4-7):** todo bien.
- **Veredicto:** fuera por (1) — no tiene scheduling nativo, viola el criterio
  explícito de F1 §5 / F2 §9.7.

### RQ (Redis Queue)
- **Licencia/coste:** BSD-2, sin coste.
- **(1) Scheduling:** **no nativo**. Requiere `rq-scheduler` (paquete aparte,
  mantenido pero independiente). Igual problema que Dramatiq.
- **(2) Cancelación:** `send_stop_job_command(connection, job_id)` envía SIGINT
  al worker.
- **(3) FastAPI async:** sync-first.
- **(4-7):** todo bien, simplicidad operativa alta.
- **Veredicto:** fuera por (1) — scheduling no nativo.

### APScheduler
- **Licencia/coste:** MIT, sin coste.
- **(1) Scheduling:** sí, **es** un scheduler — pero **no es cola + worker**: no
  hay broker, las tareas viven en el proceso del scheduler.
- **(2) Cancelación:** `scheduler.remove_job(id)` solo previene futuras
  ejecuciones; no mata una en curso.
- **(3-7):** in-process; no encaja con el modelo "API encola, worker independiente
  ejecuta" de F2 §6.5.
- **Veredicto:** **fuera por arquitectura**. APScheduler es scheduling sin cola;
  F2 pide cola + worker con scheduling como costura. Es el inverso.

## Tabla resumen

| Criterio | Celery | arq | Dramatiq | RQ | APScheduler |
|---|:---:|:---:|:---:|:---:|:---:|
| 1. Scheduling nativo | ✅ | ✅ | ❌ | ❌ | ✅* |
| 2. Cancelación mid-job | ✅ | ✅ | ⚠️ | ✅ | ❌ |
| 3. FastAPI async idiomático | ❌ | ✅ | ❌ | ❌ | n/a |
| 4. Mockeable / testeable | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5. Operable por una persona | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| 6. Redis suficiente | ✅ | ✅ | ✅ | ✅ | n/a |
| 7. Mantenimiento activo | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8. Sin licencia comercial | ✅ | ✅ | ✅ | ✅ | ✅ |

*APScheduler cumple "scheduling" pero no "cola + worker" — descalifica por (3).

## Decisión

**arq.** Cumple los 8 criterios, encaja idiomáticamente con el modelo async de
FastAPI (criterio diferencial frente a Celery), y mantiene el operativo mínimo
(un solo proceso de worker, sin `beat` separado).

**Configuración prevista (esquemática, no es código aún):**

- **Broker:** Redis (servicio `redis` del docker-compose actual; se mantiene en
  la reescritura del compose del bloque 1).
- **Worker:** un único proceso `arq app.infrastructure.jobs.worker_settings.WorkerSettings`.
- **Tareas día uno:** `run_backtest(backtest_id)`. La rotación consulta el flag de
  cancelación al inicio de cada iteración de semana (atención cooperativa).
- **Scheduling (costura, no día uno):** placeholder vacío en `WorkerSettings.cron_jobs`;
  cuando se quiera refrescar precios programadamente, se enchufa ahí sin cambiar
  el worker.
- **Logging correlacionado** (F2 §7.1): el `job_id` de arq se propaga como
  identificador del log; convive con el `backtest_id` que ya es el correlator
  principal.

**Por qué no Celery:**

Celery es la opción "segura" por madurez, pero su modelo sync obliga a una rama
del backend con estilo distinto al resto (no-async), introduce un proceso extra
(`beat`), y su cancelación mid-job es menos idiomática. arq cubre los mismos
criterios sin esos costes. La madurez de Celery sería decisiva si necesitáramos
features de su ecosistema (chains, chords, retries con backoff fino, prioridades,
múltiples brokers); F2 §6.5 no las pide día uno y su aparición sería un cambio
de tooling (registrable como ADR sucesor).

## Alternativas descartadas

- **Celery** — por modelo sync y operativo más pesado, ver arriba.
- **Dramatiq** — sin scheduling nativo (incumple F1 §5 / F2 §9.7).
- **RQ** — sin scheduling nativo (incumple F1 §5 / F2 §9.7).
- **APScheduler** — no es cola + worker (incumple el modelo asíncrono de F2 §6.5).
- **Implementación a medida sobre `asyncio.Task`** — no es "herramienta de jobs";
  perdemos persistencia de cola (un reinicio mata los jobs), cancelación, y
  scheduling. Falso ahorro.

## Consecuencias

**Más fácil:**
- El código del worker se escribe en el mismo estilo async que el resto del
  backend (sin "rama sync" paralela).
- La costura del scheduler queda **realmente gratis**: añadir un cron job
  es declararlo en `WorkerSettings.cron_jobs`, sin nuevos procesos ni librerías.
- Cancelación cooperativa simple: un `await ctx.abort_aborted()` (idiom de arq)
  al inicio de cada iteración de semana.
- Tests e2e (F2 §8.4): arq ofrece helpers de test que arrancan/paran el worker
  contra Redis real.

**Más difícil:**
- Comunidad menor que Celery → para problemas raros puede haber menos
  documentación disponible; queda mitigado por que el autor (Samuel Colvin) y la
  base de usuarios son técnicos (no es un proyecto huérfano).
- Si en el futuro se quisieran features de Celery (chains, prioridades), migrar
  a Celery sería un cambio de tooling con su propio ADR. **Costura:** las tareas
  se escriben como funciones puras con efectos en repositorios + puertos,
  inmunes a la migración futura (el adaptador es lo que cambia).

**Dependencia nueva justificada:**
- `arq` (paquete Python). Justificación: cumple criterio F1 §5 / F2 §9.7. No
  hay alternativa equivalente sin la misma adición.
- No se añade Celery ni se requieren librerías de scheduling externas.

**Sin coste de licencia.**

## Pregunta abierta a producto

¿Hay alguna feature de Celery que ya esté en mente para más adelante
(p.ej. workflows complejos con dependencias entre tareas, prioridades, fan-out)
que pesara más que la elegancia async? Si la respuesta es no, esta decisión
queda firme. Si la respuesta es sí, esta ADR queda como *propuesta* sujeta a
discusión.
