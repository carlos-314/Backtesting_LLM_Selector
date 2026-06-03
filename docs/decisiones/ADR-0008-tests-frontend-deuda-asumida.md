# ADR-0008 — Tests automatizados de frontend: deuda asumida día uno

**Fecha:** 2026-06-03
**Estado:** aceptada
**Toca contrato de fase previa:** No — formaliza una omisión de planificación de F3
y la deuda que se asume conscientemente al cerrar la construcción.

## Contexto

F2 §8 define una estrategia de testing **innegociable** para el backend
(pirámide sesgada al dominio, integración real en costuras, e2e mínimo
sobre flujos clave). F3 (UI) **no define una estrategia equivalente** para
el frontend; el etiquetado de F3 §10 sobre componentes y vistas describe
contratos y estados pero no exige pruebas automatizadas.

Al cerrar la fase 3 de construcción (puerta bloqueante registrada en
`docs/CIERRE-F3.md`), el backend supera el listón:
- **355/355 tests verde**.
- **Dominio 97% líneas / 96% ramas** (cumple "innegociable").
- **5/5 flujos críticos de F2 §8.4** cubiertos end-to-end.

El **frontend** queda con:
- TypeScript `tsc -b --noEmit` verde.
- `vite build` verde.
- Smoke runtime manual (login + navegación) verificado en `localhost:5173`
  contra backend real en `localhost:18000`.
- **0 tests automatizados** (unit, integration, e2e).

Negocio elige cerrar la fase con esta deuda registrada en lugar de
extender el alcance ~12h para cubrir la pirámide.

## Decisión

Cerrar la fase 3 de construcción con **el frontend sin suite de tests
automatizados**, asumiendo conscientemente la deuda. Los criterios de
validación operativa día uno para el frontend son:

1. `tsc -b --noEmit` verde en CI (`.github/workflows/ci.yml`).
2. `vite build` verde en CI.
3. Verificación manual del flujo principal (login → mapa → ficha → backtest
   nuevo → polling → resultado) antes de promover entre ramas.

## Alternativas descartadas

- **Cubrir la pirámide de F2 §8 también para el frontend** (~12h adicionales):
  Vitest + Testing Library para componentes base/dominio, MSW para hooks,
  Playwright para los flujos críticos. Aporta seguridad de regresión pero
  retrasa el cierre de la fase para una entrega que el usuario quiere ya
  funcional. **Razón de descarte:** prioridad temporal sobre cobertura;
  reabrible cuando aparezca el primer bug de regresión que la pirámide
  habría atrapado.
- **Subconjunto mínimo: solo Playwright e2e (~4h)** para los 3 flujos
  críticos del usuario final. Aporta el 80% del valor con el 30% del
  esfuerzo. **Razón de descarte:** el usuario elige el cierre sin gap; si
  el primer incidente revela que faltaba esto, abrimos ADR sucesor.
- **Snapshot tests sobre la galería `/__examples`**: barato pero ruidoso
  (los snapshots fallan ante refactor estético inocuo). Descartado por
  baja relación señal/ruido.

## Consecuencias

**Más fácil ahora**:
- Cierre de F3 inmediato.
- Sin nueva dependencia (Vitest, MSW, Playwright) ni configuración CI extra.
- Sin tiempo de mantenimiento de tests frontend mientras la UI todavía es
  joven y propensa a cambios visuales.

**Más difícil después**:
- Cualquier regresión de comportamiento (estados de servidor, polling,
  cancelación cooperativa, RoleGate, manejo de 401) **solo se detecta por
  uso real** o smoke manual.
- Refactors grandes del frontend irán "a ciegas" sin red de seguridad.
- Si el equipo crece, la falta de baseline de tests frontend dificulta el
  onboarding (no hay "ejemplo de cómo testear esto").

**Deuda explícita registrada para reabrir**:
- Si aparece **un solo bug de regresión** que un test habría atrapado, este
  ADR queda **sucedido**: hay que abrir el plan de los ~12h del CIERRE-F3.md §3.
- Si se decide promover a producción con usuarios externos (no solo equipo
  interno), reabrir esta decisión **antes** del primer despliegue público.

**Sin dependencia nueva.**

## Lista de cobertura suplida por validación manual (registro)

Estos paths quedan sin test programático y deben verificarse manualmente
en cada promoción `main` → producción:

- Login con Google (id_token válido → JWT propio).
- Login fallido (email no autorizado → `/sin-acceso`).
- Navegación de la matriz con cambio de ventana de semanas.
- Click en celda de matriz → ficha de empresa.
- Lanzar backtest: form validation + 422 invalid_period → mensaje junto al campo.
- Polling del resultado: estado pending → running → completed sin recargar.
- Cancelación de backtest running.
- `RoleGate`: viewer no ve el botón "Lanzar"; analyst sí.
- 401 transversal: si el token expira, próxima petición → login.

## Referencia operativa

`docs/CIERRE-F3.md` §3 contiene el plan detallado para cerrar el gap
cuando se decida.
