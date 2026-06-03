# ADR-0003 — Filtros y ordenación en `GET /weeks/{week_date}/companies` (R2)

**Fecha:** 2026-06-03
**Estado:** propuesta — **requiere validación humana antes de aplicar**
**Toca contrato de fase previa:** Sí → F2 §6.4 (Screening) y F3 §9 (R2)

## Contexto

F2 §6.4 deja en el contrato: `"Query: limit, cursor, sort, filtros por métrica (a concretar)"`.
Es decir, F2 acepta que `sort` y filtros existen pero no los cierra. F3 §9 lo
registra como **R2**, ligado a la interacción de filtrado/orden del visor.

Aunque V-MATRIX es la vista corazón del día uno y se sirve con un endpoint propio
(ver ADR-0001), F2 §6.4 prevé también el listado plano de empresas de una semana
(`GET /weeks/{w}/companies`) — útil para vistas que no son la matriz (panel,
exploración por una semana concreta). Sin un acuerdo sobre `sort` y filtros, el
endpoint sale día uno con un orden arbitrario y sin posibilidad de criba, lo que
es funcional pero pobre.

A la magnitud confirmada (decenas de empresas por semana), filtrar y ordenar en
cliente sería trivial. Pero el contrato de F2 cierra `limit + cursor` opaco
(F2 §6.1) y eso obliga a que el orden y el filtro se apliquen **en el servidor**:
un cursor opaco solo es estable si el orden es estable, y solo lo es si el orden
es del servidor.

## Decisión

Concretar `sort` y filtros en el endpoint, con criterio mínimo día uno que cubre
el uso real sin abrir un sistema de filtros genérico.

### Sort

**Parámetro `sort`**, opcional, formato `{campo}:{asc|desc}`. Valores cerrados (enum):

- `ticker:asc` (default si no se especifica)
- `ticker:desc`
- `name:asc`
- `name:desc`
- `valuation.ev_ebit_1y_fwd:asc` / `:desc`
- `valuation.per_1y_fwd:asc` / `:desc`
- `growth.rev_growth_1y:asc` / `:desc`
- `quality.roce_roi_1y:asc` / `:desc`
- `in_portfolio:desc` (las seleccionadas primero; útil para distinguir picks de
  resto del universo en la misma vista)

Si `sort` no está en el enum → `400 invalid_sort`. Esto es lo mismo que hace
F3 §4.2 / I4 con la lista de backtests: no se promete lo que el contrato no da.

**Estabilidad del orden:** todos los `sort` usan **clave secundaria implícita
`ticker:asc`** para garantizar orden total estable (necesario para el cursor opaco
de F2 §6.1). Dos filas con mismo valor del campo principal se desempatan por
`ticker:asc`.

**`null` y orden:** los valores `null` (regla F2 §6.4) van **al final** en orden
`asc` y al principio en `desc`. La UI debe seguir mostrando "—" en la celda,
nunca 0.

### Filtros

**Parámetros de query (opcionales, AND entre ellos):**

- `q={texto}` — búsqueda libre por `ticker` o `name` (case-insensitive,
  contains). Útil para localizar una empresa concreta.
- `in_portfolio={true|false}` — filtra por si fue seleccionada (cruce con
  `portfolios` del run resuelto).
- `country={ISO-2}` — filtra por país de cotización (ej. `US`, `CA`).
- `min_ev_ebit_1y_fwd={float}` / `max_ev_ebit_1y_fwd={float}` — rango sobre la
  métrica indicada. **Solo** sobre métricas listadas en el enum de `sort` (mismo
  conjunto, coherencia interna).

**Filtros NO incluidos día uno:**
- Filtros sobre campos `qualitative.*` (JSONB del LLM): la búsqueda dentro de un
  JSONB libre exige operadores específicos (`@>`, `?`) y conviene posponer hasta
  saber qué se filtra de verdad.
- Filtros multivalor (`country=US,CA`): el OR explícito complica la semántica;
  si llega demanda, AD-Rs futuros.
- Filtros por rango sobre `qualitative` (LLM-generated): igual que el anterior.

**Comportamiento ante filtro vacío:**
- Si el filtro vacía completamente la respuesta → `200` con `items: []`. **No es
  un error** (F3 §5.1: "Vacío — petición correcta sin datos").

### Errores

- `400 invalid_sort` — `sort` fuera del enum.
- `400 invalid_filter` — filtro con valor mal tipado (ej. `min_X` no es float).
- `422 incompatible_filter` — filtro coherente sintácticamente pero sin sentido
  (ej. `min_X > max_X`).
- Resto como F2 §6.4 (`404 week_not_found`, `502`, `500 analysis_schema_mismatch`).

### Implementación en backend

- **Sort** se traduce a `ORDER BY` en SQL contra `processed_stocks` (los nombres
  limpios del enum se mapean a las columnas sucias de origen en la ACL).
- **Filtros** se traducen a `WHERE`. `q` usa `ILIKE '%{q}%'` sobre `Ticker` y
  `Nom` (con el `q` parametrizado, no concatenado — defensa SQL injection).
- **`in_portfolio`** se calcula con `EXISTS` contra `portfolios` filtrando por
  `id_run = resolved_run_id`. El cruce vive en la ACL para mantener al dominio
  ajeno al SQL.

## Alternativas descartadas

- **Filtros y sort en cliente, paginación en servidor** — incompatible con el
  cursor opaco (F2 §6.1): un cursor solo es estable si el orden lo es; ordenar
  en cliente "después de paginar" rompe orden global.
- **Sistema de filtros genérico tipo `?filter[field][op]=value`** — sobre-diseño
  para el día uno; abre superficie de validación enorme; F0 no lo pide.
- **GraphQL para esta query** — añade dependencia y modelo paralelo; el resto del
  contrato F2 es REST con cursor opaco y conviene homogéneo.
- **Ordenar por columnas `qualitative.*`** — son JSONB libres del LLM, no
  comparables; el orden por ellas no es semánticamente útil.

## Consecuencias

**Más fácil:**
- El visor puede ofrecer filtros simples (búsqueda, picks-only, país, rangos sobre
  métricas centrales) sin trasladar lógica a cliente.
- El cursor opaco de F2 §6.1 queda coherente: orden estable garantizado por la
  clave secundaria `ticker:asc`.

**Más difícil:**
- Cada `sort`/filtro nuevo requiere ADR sucesor (lista cerrada). Asumido como
  precio de evitar deuda de diseño abierto.
- El cruce `in_portfolio` añade un EXISTS por fila; a la escala (decenas de
  empresas por semana) es trivial.

**Deuda asumida:**
- Sin filtros sobre `qualitative.*` día uno. Si negocio pide filtrar por p.ej.
  "menciona 'AI'" en el dossier, será otro ADR — necesita operadores JSONB.

**Sin dependencia nueva.**

## Pregunta abierta a producto

¿El conjunto de `sort` y filtros propuesto cubre el uso real del visor día uno, o
hay alguna criba imprescindible que falte (ej. filtrar por sector, por
recomendación de analista, por rango de capitalización)?
