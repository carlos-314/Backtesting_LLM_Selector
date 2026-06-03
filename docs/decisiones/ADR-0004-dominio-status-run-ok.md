# ADR-0004 — Dominio de `analysis_runs.status` y regla "run OK" para `WeekResolver`

**Fecha:** 2026-06-03
**Estado:** aceptada
**Toca contrato de fase previa:** No (resuelve la **acción bloqueante F2 §3.1 / CLAUDE.md tareas bloqueantes** — verificar el dominio antes de implementar `WeekResolver`)

## Contexto

F2 §3.1 deja como **acción de construcción bloqueante** verificar contra Railway
el dominio real de `analysis_runs.status` y de los campos `error`/`proceso`/
`traceError` de `stock`/`processed_stocks`, antes de implementar el `WeekResolver`,
para definir qué valor(es) significan "run terminado correctamente".

F2 §3.1 establece además una **regla provisional fail-safe**: cualquier valor no
reconocido como "OK" se trata como NO OK.

Esta ADR documenta la verificación realizada y cierra la decisión.

## Verificación realizada

Inspección directa contra Railway con el usuario `app_reader` (read-only):

### Dominio observado de `analysis_runs.status`

Solo dos valores presentes en 28 runs:

| status        | runs | con `analisis_global` | con `descripcion` | runs sin picks |
|---------------|-----:|----------------------:|------------------:|---------------:|
| `'COMPLETED'` |   15 |                    15 |                15 |              0 |
| `'STARTED'`   |   13 |                    11 |                13 |              4 |

**No hay valores `NULL`, ni espacios extraños, ni otros estados.**

Patrón observado:
- `'COMPLETED'` se correlaciona con runs íntegros: 15/15 con análisis global,
  15/15 con al menos 1 pick en `portfolios`.
- `'STARTED'` es el `DEFAULT` del esquema (`VARCHAR(50) DEFAULT 'STARTED'`).
  Se queda pegado tanto en runs en curso recientes (ej. `id_run=41`,
  `fechaRun=2026-06-01`, 2 días antes de la inspección) como en runs antiguos
  que probablemente se quedaron a medio cocer (4 de 13 sin picks).

### Dominio observado de campos relacionados (informativo)

- **`processed_stocks.status`** (4 valores: `LLM_OK`, `FINANCIALS_OK`, `PENDING`,
  `LLM_DOSSIER_OK`) — es un estado **por fila** dentro del pipeline; no informa
  sobre la completitud del *run* en su conjunto.
- **`stock.error` / `stock.proceso` / `stock.traceError`** — son campos de
  control de las rutinas de descarga (yfinance/scraping) por *ticker*, no por run.
  No deben usarse para decidir si un run es OK.
- **`processed_stocks` NO tiene columnas `error`/`proceso`/`traceError`**.
  F2 §3.1 menciona estos campos como residentes en `stock` *y* `processed_stocks`;
  en realidad solo están en `stock`. **Inexactitud menor de F2 §3.1** registrada
  para conocimiento, sin más impacto.

## Decisión

**Definición de "run terminado correctamente" para el `WeekResolver`:**

Un run se considera **OK** si y solo si se cumplen *ambas* condiciones:

1. `analysis_runs.status = 'COMPLETED'` (literal, case-sensitive).
2. Tiene al menos **1 pick** en `portfolios` para ese `id_run`.

**Todo lo demás es NO OK**, incluidos:
- `status = 'STARTED'` (default; queda pegado en runs incompletos).
- `status` con cualquier otro valor (futuro, desconocido, NULL, etc.) — aplica la
  regla fail-safe de F2 §3.1.
- `status = 'COMPLETED'` pero **sin picks** en `portfolios` (no observado en los
  datos actuales pero defensivo).

**Por qué la condición 2 (presencia de picks) además de la 1:**

F1 §7.3 exige "validación defensiva: fallar de forma clara y diagnosticable si el
esquema externo no coincide, nunca producir resultados silenciosamente
incorrectos." Un run `COMPLETED` sin picks rompería el contrato del
`WeekResolver` (la semana resolvería a un run válido pero sin selección, lo que
luego haría que un backtest tuviera una semana sin entradas). El caso no se
observa hoy; queda atrapado defensivamente.

**Comportamiento al encontrar un run NO OK:**

- El `WeekResolver` lo **ignora** al agrupar runs por semana (busca el siguiente
  candidato; si no hay otro `OK` en la misma semana, la semana queda sin run
  resuelto → no se muestra ni entra en backtests).
- Se **loguea** estructuradamente (F2 §7.1): `event=run_not_ok`,
  `id_run`, `status`, `reason` (`status_not_completed` / `no_picks` /
  `status_unknown_failsafe`). El log permite distinguir las tres causas sin
  abrir queries manuales.

**Validación defensiva sobre el dominio del propio campo:**

Si la ACL encuentra un valor de `status` **no contemplado** por este ADR (es decir,
no `'COMPLETED'` ni `'STARTED'`), trata el run como NO OK (fail-safe) **y**
emite `analysis_schema_mismatch` a nivel de aviso (no fatal): se registra el
valor inesperado para que el equipo lo revise. No bloquea el resto de los runs.

## Alternativas descartadas

- **Solo la condición 1 (`status = 'COMPLETED'`)** — más sencillo y suficiente
  para los datos actuales (15/15 COMPLETED tienen picks), pero pierde la red
  defensiva de F1 §7.3 ante un `COMPLETED` corrupto futuro.
- **Más condiciones (analisis_global no nulo, processed_stocks > N filas)** —
  añade ruido sin beneficio claro. `analisis_global` no es necesario para
  resolver una semana (sí lo es para la vista de resumen semanal, pospuesta);
  el conteo de processed_stocks varía legítimamente (1461 vs 1467 de media en
  los dos buckets). La condición 2 (picks) es la mínima necesaria para que un
  run sea *útil* a backtest y visor.
- **Aceptar `'STARTED'` como OK si tiene picks y análisis** — algunos `STARTED`
  parecen runs terminados que no se cerraron; aceptarlos *podría* recuperar 9
  runs adicionales. Descartada: viola fail-safe (F2 §3.1) y mezcla "completado"
  con "en curso". Si negocio quiere rescatar esos runs, lo correcto es **cerrar
  el pipeline externo** para que actualice el status a `COMPLETED`, no relajar
  la regla del consumidor.
- **Diccionario configurable de valores OK** — sobre-diseño; introduciría
  superficie de configuración para 2 valores conocidos.

## Consecuencias

**Más fácil:**
- El `WeekResolver` se implementa con un predicado simple y testeable
  (`is_ok(run): return run.status == 'COMPLETED' and run.pick_count > 0`).
- Los tests unitarios del `WeekResolver` (F2 §8.1) ya tienen el caso "OK" y los
  tres casos NO OK (`status_not_completed`, `no_picks`, `status_unknown_failsafe`)
  bien definidos. Convención de nombres: `test_resolver_run_completed_con_picks_es_ok`,
  `test_resolver_status_started_no_es_ok`, `test_resolver_status_desconocido_aplica_failsafe`,
  `test_resolver_completed_sin_picks_no_es_ok`.

**Más difícil:**
- Si en el futuro aparece un tercer valor legítimo de `status` (ej. el pipeline
  externo añade `COMPLETED_WITH_WARNINGS`), un nuevo ADR debe ampliar esta
  decisión, no relajarse en código.

**Deuda asumida:**
- Los 13 runs en `STARTED` actuales se ignoran. Si alguno de ellos es realmente
  un run "OK" mal cerrado, queda fuera del visor y de los backtests. Mitigación:
  el log estructurado permite identificarlos y, si negocio lo confirma, el
  pipeline externo puede corregir el status (no la app).

**Sin dependencia nueva.**

## Anexo — comando de inspección reproducible

```sql
SELECT status, COUNT(*) FROM analysis_runs GROUP BY status;

SELECT r.status, COUNT(*) AS runs,
       SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id_run = r.id_run)
                THEN 1 ELSE 0 END) AS without_picks
FROM analysis_runs r GROUP BY r.status;
```

Ejecutado el 2026-06-03 con `app_reader` contra Railway. La inspección se puede
repetir periódicamente; si el dominio cambia, abrir ADR sucesor.
