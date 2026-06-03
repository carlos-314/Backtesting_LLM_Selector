# ADR-0006 — `app_user.google_id` NULLABLE + alta de usuarios por admin

**Fecha:** 2026-06-03
**Estado:** aceptada
**Toca contrato de fase previa:** Sí → F2 §5.1 (`google_id NOT NULL`) y F2 §6.3 (alta de invitados aplazada)

## Contexto

F2 §5.1 modela `app_user.google_id` como `NOT NULL UNIQUE`. F2 §6.3
documenta el error `403 user_not_authorized` con el comentario *"el alta de
invitados está aplazada, día uno = 'no estás en la lista'"*.

F1 §5 lo refina: la **UI** de admin se aplaza, pero el **mecanismo** existe
día uno — *"alta manual el día uno, **escribiendo en las mismas tablas que
luego usará la pantalla**"*.

Aparece un problema huevo-y-gallina:

- Para pre-autorizar a un email concreto, el admin necesita escribir una fila
  en `app_user` ANTES de que ese usuario haga login.
- Pero `google_id` (el `sub` del JWT de Google) sólo se conoce DESPUÉS del
  primer login.
- Con `google_id NOT NULL`, no se puede pre-insertar.

Negocio (esta sesión) aclara la directiva día uno:

> *"Solo quiero que puedan entrar si el admin ha autorizado la dirección de
> correo. El correo del admin es carlos.picazo.314@gmail.com. Que haya una
> opción para dar de alta el correo de un usuario y asignar su role."*

Esto exige: pre-alta por email + role; auto-vinculación de `google_id` en el
primer login del email pre-aprobado.

## Decisión

1. **`app_user.google_id` pasa a `NULLABLE` (UNIQUE conservado)**. Permite
   pre-insertar filas con `email + role + google_id=NULL`. UNIQUE sigue
   protegiendo contra colisiones tras la vinculación.
2. **Flujo de alta**:
   - **Bootstrap inicial** (al arrancar el backend): si la tabla `app_user`
     está vacía y `INITIAL_ADMIN_EMAIL` está en `.env`, insertar un row con
     `email=$INITIAL_ADMIN_EMAIL, role='admin', google_id=NULL`. Idempotente.
   - **Alta por admin** (endpoint día uno): `POST /api/v1/admin/users`
     inserta `email + role`, `google_id=NULL`. Sólo `role=admin` puede.
3. **Flujo de login con vinculación**:
   1. Backend verifica `id_token` con Google → `(google_id, email)`.
   2. Busca `app_user` por `google_id`. Si encuentra: login OK.
   3. Si no: busca por `email`.
      - Si encuentra fila con `google_id IS NULL`: actualiza
        `google_id = identity.google_id`. Login OK. *(vinculación)*
      - Si encuentra fila con `google_id` distinto: `403 user_not_authorized`
        *(el email fue vinculado a otra cuenta Google previamente)*.
   4. Si tampoco por email: `403 user_not_authorized`.

## Alternativas descartadas

- **Tabla `authorized_email` separada** (sólo email + role pre-aprobado;
  `app_user` se crea en el primer login) — más limpia conceptualmente pero
  añade una tabla al modelo de F2 y obliga a sincronizar dos sitios cuando
  llegue la UI de admin. Más cambio que beneficio.
- **Whitelist en `.env`** (variable `AUTHORIZED_EMAILS`) — rompe F1 §5
  ("escribiendo en las mismas tablas que luego usará la pantalla"). La UI
  futura no podría leer un .env.
- **Mantener `google_id NOT NULL` y hacer alta tras el primer login** —
  exige que el primer login sea libre (cualquier Google account entra) y
  luego el admin elimine si no autoriza. Contradice "solo entran emails
  autorizados".

## Consecuencias

**Más fácil**:
- Una sola tabla (`app_user`) modela tanto pre-altas como usuarios activos.
- La UI de admin futura escribe en esa misma tabla (F1 §5 satisfecho).
- El bootstrap del primer admin queda como una variable de entorno: cero
  fricción para arrancar en local o producción.

**Más difícil**:
- El código de `authenticate_with_google` lleva la lógica de vinculación —
  un poco más complejo que un simple lookup por `google_id`.
- Posible confusión: una fila en `app_user` con `google_id=NULL` puede
  parecer "incompleta" en consultas SQL ad-hoc. Mitigación: comentario en
  el modelo + el ADR.

**Deuda asumida**:
- Si en el futuro F2 §5.1 se "endurece" otra vez (`google_id NOT NULL`),
  habrá que decidir cómo migrar las filas no vinculadas. Aceptable.

**Sin dependencia nueva.**

## Cambios concretos derivados

- Migración Alembic que cambia `app_user.google_id` a `NULLABLE` (UNIQUE
  conservado).
- Variable `INITIAL_ADMIN_EMAIL` añadida a `Settings` y al `.env`.
- Hook de lifespan en FastAPI que invoca `bootstrap_initial_admin` al
  arrancar.
- Endpoint `POST /api/v1/admin/users` (capacidad: `Role.ADMIN`) que crea
  filas pre-aprobadas. *(Endpoint implementado en pieza 11/12.)*
- Caso de uso `authenticate_with_google` con la vinculación descrita.
