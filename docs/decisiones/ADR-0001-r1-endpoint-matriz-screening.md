# ADR-0001 — Endpoint del mapa histórico de selección (R1)

**Fecha:** 2026-06-03
**Estado:** propuesta — **requiere validación humana antes de aplicar**
**Toca contrato de fase previa:** Sí → F2 §6.4 (Screening) y F3 §9 (R1)

## Contexto

F3 §1.3 / §1.5 / §6.2 identifica la vista **V-MATRIX (mapa histórico de selección)** como
pieza central del visor (día uno). Es una rejilla *empresa × semana* con estado por
celda (no estuvo / estuvo en universo / fue seleccionada / sin dato).

F2 §6.4 cierra los endpoints de Screening con grano de **una semana** (`GET /weeks`,
`GET /weeks/{w}/companies`, `GET /weeks/{w}/companies/{t}`, `GET /weeks/{w}/picks`).
**No existe endpoint que devuelva la matriz directamente.**

F3 §9 lo registra como **R1 — Realimentación F2 abierta**: componer la matriz en
cliente trasladaría al frontend dos reglas de dominio:
1. La **unión** del universo de empresas analizadas a lo largo de un rango de semanas.
2. La regla *"qué cuenta como seleccionada"* (parte de `WeekResolver` + lectura de `portfolios`).

Ambas pertenecen al backend (F2 §4.5: "es dominio si sería verdad aunque cambiáramos
de base de datos, framework web o fuente de precios"). Que viaje al cliente sería
una desviación del reparto de responsabilidades de F2.

La auditoría del CTO sobre F3 (§9 nota I2) ya avisó del riesgo: *"sobre este endpoint
no confirmado ya se ha invertido diseño de UI aguas abajo"*. Si no se concreta el
contrato, parte del diseño de V-MATRIX se rehace al implementarlo.

## Decisión

Añadir al contrato de F2 §6.4 un nuevo endpoint:

```
GET /api/v1/screening/matrix?from={YYYY-MM-DD}&to={YYYY-MM-DD}
```

**Parámetros:**
- `from`, `to`: fechas de calendario (`YYYY-MM-DD`), inclusivas. Cada una se interpreta
  como `week_date` canónica (lunes NY, F2 §4.3). Si una de las dos no coincide con un
  lunes NY, se redondea al lunes que contiene esa fecha. Si `from > to` → `400`.
- Tope de rango: máximo 156 semanas (≈3 años, alineado con F3 §1.3 *"hacia atrás hasta
  ~3 años"*). Más → `422 range_too_wide`.

**Respuesta `200 OK` (forma propuesta, ejes resueltos + celdas dispersas):**

```json
{
  "weeks": [
    { "week_date": "2026-01-05", "run_code": "RUN-2026-W01", "resolved_run_id": 42 },
    { "week_date": "2026-01-12", "run_code": "RUN-2026-W02", "resolved_run_id": 47 }
  ],
  "companies": [
    { "ticker": "AAPL", "name": "Apple Inc.", "country": "US", "currency": "USD" },
    { "ticker": "MSFT", "name": "Microsoft Corp.", "country": "US", "currency": "USD" }
  ],
  "cells": [
    { "ticker": "AAPL", "week_date": "2026-01-05", "state": "selected" },
    { "ticker": "AAPL", "week_date": "2026-01-12", "state": "in_universe" },
    { "ticker": "MSFT", "week_date": "2026-01-05", "state": "in_universe" }
  ]
}
```

**Estados de celda** (cerrados, enum):
- `selected` — el ticker estaba en `portfolios` del run resuelto de esa semana.
- `in_universe` — el ticker estaba en `processed_stocks` del run resuelto pero no en `portfolios`.
- *(omisión)* — el ticker no estaba en ese run; ausencia de celda = "no estuvo".

**Justificación de la forma "dispersa con ejes resueltos":**

1. **Ejes resueltos:** la lista de `weeks` ya tiene `resolved_run_id` aplicado por el
   `WeekResolver` (último run OK), no expone runs crudos. Coherente con F2 §4.6
   (la ACL produce read models limpios).
2. **Lista de `companies` separada:** evita repetir nombre/país/divisa en cada celda
   (a 50 empresas × 156 semanas son 7.800 celdas; repetir metadata es waste).
3. **Celdas dispersas:** "no estuvo" es ausencia (regla null≠0 de F2 §6.4: la matriz
   distingue *no estuvo* de *sin dato*; `sin dato` no aparece en este endpoint porque
   significa "el run de esa semana no devolvió análisis para ese ticker" — caso
   degenerado, no esperado bajo F2 §3.1; si aparece, se loguea como
   `analysis_schema_mismatch` antes de servirlo).
4. **Sin paginación:** la magnitud confirmada por F3 §9 R1 ("decenas de empresas ×
   26–150 semanas") da en peor caso ~7.800 celdas + ~150 weeks + ~50 companies ≈
   payload de pocos cientos de KB. Pagina si en algún momento se prueba que crece;
   día uno no.

**Errores:**
- `400 bad_request` — `from`/`to` mal formados, `from > to`.
- `422 range_too_wide` — más de 156 semanas.
- `502 analysis_unreachable`, `500 analysis_schema_mismatch` — como el resto de
  Screening (F2 §6.4).

**Autorización:** sesión válida (cualquier rol). Read-only.

## Alternativas descartadas

- **Componer en cliente** (llamando N veces a `GET /weeks/{w}/companies` + `/picks`) —
  arrastra dos reglas de dominio (unión + "qué cuenta como seleccionada") al
  frontend; viola la frontera 3↔4 de F3 §3.1 y F2 §4.5; además, N peticiones contra
  la ACL son N validaciones defensivas redundantes y un pico de carga innecesario.
- **Forma "densa" (matriz NxM completa con `null` para celdas vacías)** —
  duplica peso del payload y mezcla `null`-de-ausencia con la regla null≠0;
  prefer dispersa.
- **Dos endpoints** (`GET /screening/matrix/axes` + `GET /screening/matrix/cells`) —
  añade un round-trip sin ganancia clara; las celdas dependen de los ejes resueltos,
  separar invita a inconsistencia.
- **Granularidad alternativa**: matriz mensual o por trimestre. Descartada: F2 §4.3
  fija que la unidad temporal del dominio es la *semana*; cambiarlo aquí
  contradiría F2.

## Consecuencias

**Más fácil:**
- V-MATRIX se construye sin reescribir lógica de dominio en cliente.
- La validación defensiva (F2 §3.1, §7.3) sigue ocurriendo en un solo sitio (ACL
  + WeekResolver) en vez de N veces en el front.
- Comparar performance/observabilidad (un endpoint, un trace) frente a N peticiones.

**Más difícil:**
- Aparece un endpoint nuevo en el contrato de F2. Hay que **versionarlo dentro de
  `/api/v1`** y mantenerlo estable a 5 años.
- El test de integración de la ACL ahora cubre también este caso (no es coste extra
  significativo; F2 §8.3 ya pide ACL contra base real).

**Deuda asumida:**
- El tope de 156 semanas es un parámetro de diseño; si el negocio lo amplía, el
  endpoint sigue funcionando pero conviene revisar el peso del payload.

**Sin dependencia nueva:** no introduce librerías ni servicios externos.
