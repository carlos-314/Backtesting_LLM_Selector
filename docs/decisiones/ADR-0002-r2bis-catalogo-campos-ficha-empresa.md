# ADR-0002 — Catálogo de campos de la ficha de empresa (R2-bis)

**Fecha:** 2026-06-03
**Estado:** propuesta — **requiere validación humana antes de aplicar**
**Toca contrato de fase previa:** Sí → F2 §6.4 (`GET /weeks/{week_date}/companies/{ticker}`) y F3 §3.3/§4.3/§9 (R2-bis)

## Contexto

F2 §6.4 deja la ficha `GET /weeks/{week_date}/companies/{ticker}` con respuesta
**"objeto completo (incl. cualitativos LLM)"**, sin enumerar qué campos. F3 §9 lo
registra como **R2-bis** porque sin el catálogo los componentes
`CompanyMetrics`/`CompanyQualitative` del estrato 3 (F3 §3.3) tienen su contrato de
props **pendiente** y la auditoría del CTO (C1) lo marcó como crítico.

La tabla origen es `processed_stocks` de la legacy de Railway: **128 columnas**,
mezcla cuantitativos + analyst consensus + ownership flows + 16 campos JSONB con
salidas LLM. Exponer las 128 al cliente sería leak de detalle interno y arrastraría
el casing sucio (`"MOD1Y EV/EBIT"`, `"1YEBIT"`) a la API pública.

La ACL (F2 §4.4) es el sitio donde se traduce el casing sucio a nombres limpios;
qué se traduce y qué no es decisión de producto, no técnica.

## Decisión

Definir el catálogo de la respuesta en **tres bloques semánticos**, traducidos por
la ACL a `snake_case` limpio. **La respuesta no expone las 128 columnas; expone un
subconjunto curado.** El catálogo concreto se documenta en F2 (no aquí) cuando se
valide. Esta ADR fija la **estructura** y el **criterio de selección**, no la lista
de campos.

**Estructura de la respuesta `200 OK`:**

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "country": "US",
  "exchange": "NASDAQ",
  "currency": "USD",
  "week_date": "2026-01-05",
  "run_code": "RUN-2026-W01",
  "in_portfolio": true,
  "portfolio_role": "core",

  "valuation": {
    "ev_ebit_1y_fwd": 18.4,
    "ev_ebitda_1y_fwd": 14.2,
    "per_1y_fwd": 22.1,
    "p_fcf_1y_fwd": 28.0
  },
  "growth": {
    "rev_growth_1y": 0.08,
    "rev_growth_3y_cagr": 0.11,
    "anal_rev_growth": 0.10
  },
  "quality": {
    "roce_roi_1y": 0.35,
    "fcf_1y": 95000000000,
    "gross_margin_median": 0.42,
    "net_debt_ebitda_1y": -1.2
  },
  "capital_allocation": {
    "buyback_yield_3y": 0.03,
    "dividend_yield_3y": 0.005
  },
  "sentiment": {
    "analyst_recommendation": "buy",
    "analyst_num_estimates": 32
  },

  "qualitative": {
    "executive_directive": { ... },
    "growth_drivers": { ... },
    "management_quality": { ... },
    "fraud_risk": { ... },
    "macro_sensitivity": { ... },
    "competitive_position": { ... },
    "final_dossier": "Texto largo del LLM…"
  }
}
```

**Criterios para incluir/excluir campos cuantitativos:**

Un campo entra en la ficha si cumple **al menos uno** de:
1. **Es relevante para la decisión de inversión** mostrada en F0 (visor que ayuda a
   justificar el screening).
2. **Es comparable entre empresas** (escala normalizada o ratio).
3. **Es parte del rationale del LLM** (citado en `qualitative.*`).

Quedan **fuera de la ficha día uno**:
- Campos de pipeline interno: `error`, `proceso`, `traceError`, `status`,
  `fecha_processament`, `LimitarMultiplos`, `ciclica`, `Last2QEBIT` (forma libre,
  no comparable).
- Datos crudos sin aportar al juicio: `1YShares`, `1YNetDebt`, `LTMEV`,
  `MedianGrossMargin` (preferimos su ratio derivado).
- Ownership flows desagregados (Insider/Guru/Mutual/Institutional Buying/Selling
  individuales): si los queremos, primero hay que decidir cómo presentarlos
  comparablemente.
- Revenue forecasts trimestrales (`NextQ1..Q4Revenue`): no útiles a grano de ficha,
  sí potencialmente a grano de modelo financiero (fuera de alcance día uno).

**Reglas transversales (heredadas):**
- **`null` ≠ `0`** (F2 §6.4, F3): un campo ausente en `processed_stocks` se serializa
  como `null` en JSON. La UI lo pinta `"—"` / `"sin dato"`, **nunca 0**.
- **Casing**: `snake_case` en JSON; la ACL traduce desde el casing sucio de origen.
- **Validación defensiva** (F2 §3, §7.3): si la columna esperada no existe en
  `processed_stocks` → `500 analysis_schema_mismatch` con `code` legible.

**Bloque `qualitative.*`:** cada subcampo corresponde a un JSONB de
`processed_stocks` (`AIDirectiva2`, `aValoresCrecimiento2`, `calidadDirectiva5`,
`potencialFraude8`, `sensibilidadMacro1`, etc.). La ACL **no inspecciona** la
estructura interna del JSONB (es libre, generada por el LLM): se pasa tal cual
bajo un nombre limpio.

**Campos contextuales:**
- `in_portfolio` y `portfolio_role`: derivados del cruce con `portfolios` del
  `resolved_run_id`. Es lo que la ficha necesita para mostrar "fue seleccionada"
  o "no fue seleccionada".

## Alternativas descartadas

- **Exponer las 128 columnas raw** — leak de detalle interno; arrastra el casing
  sucio a la API; obliga al frontend a saber qué columna es qué.
- **Catálogo definido por el frontend** — viola la frontera SPA↔API (F1 §3): el
  contrato lo posee el backend.
- **Respuesta plana sin bloques semánticos** — pierde la agrupación que la UI ya
  necesita (`CompanyMetrics` agrupa visualmente por valoración / crecimiento /
  calidad / etc.); F3 §3.3 lo asume.
- **Catálogo "más es mejor" (todo lo que no sea control de pipeline)** — convierte
  la decisión en "qué excluir" en vez de "qué incluir"; ruido en la ficha y
  acoplamiento a 128 nombres.

## Consecuencias

**Más fácil:**
- `CompanyMetrics` y `CompanyQualitative` (F3 §3.3) pueden cerrar su contrato de
  props sobre los nombres limpios.
- La ACL tiene una única responsabilidad clara: traducir 128 columnas sucias a un
  catálogo limpio bien delimitado.
- Añadir un campo nuevo es una decisión visible (entra en este ADR o en su
  sucesor), no aparece silenciosamente.

**Más difícil:**
- Es trabajo de producto, no técnico: el catálogo concreto necesita validación de
  negocio (qué métricas son las que de verdad sustentan la decisión). Este ADR
  propone una lista de **partida** sujeta a revisión.

**Deuda asumida:**
- Día uno la ficha quizá no muestre todo lo que algún día interese. Añadir
  campos es enchufable (entran como columnas a la ACL); quitar es ruidoso.

**Sin dependencia nueva.**

## Pregunta abierta a producto

¿La lista propuesta en `valuation`/`growth`/`quality`/`capital_allocation`/
`sentiment` es la correcta para el día uno, o hay campos imprescindibles que
falten y otros que sobren? Este ADR queda en *propuesta* hasta tener tu respuesta.
