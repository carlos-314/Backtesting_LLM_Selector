# ADR-0007 — Bearer JWT en cuerpo, sin refresh tokens día uno

**Fecha:** 2026-06-03
**Estado:** aceptada
**Toca contrato de fase previa:** Sí → F2 §6.1 (transporte de sesión), §6.3 (`/auth/*`)

## Contexto

F2 §6.1 deja el transporte de sesión como "detalle de construcción":

> *"El transporte de la sesión (cookie httpOnly vs token en cuerpo) queda
> como **detalle de construcción**, no se fija en el contrato."*

F2 §6.3 enumera tres endpoints de auth (`POST /auth/google`, `POST /auth/logout`,
`GET /auth/me`) pero **no menciona `/auth/refresh`**. El config heredado del
esqueleto trae `JWT_REFRESH_TOKEN_EXPIRE_DAYS=7` y `create_refresh_token()`
en `security.py`, pero ningún endpoint los consume.

Hay que cerrar:
1. ¿Bearer en JSON body o cookie HTTPOnly?
2. ¿Refresh tokens día uno o no?

## Decisión

**Bearer JWT en JSON body, sin refresh tokens día uno.**

### Transporte de la sesión

- El backend emite `access_token` (JWT firmado con `JWT_SECRET`).
- El frontend lo guarda en memoria (no localStorage) y lo envía en
  `Authorization: Bearer <token>` en cada petición autenticada.
- **NO** se usan cookies HTTPOnly día uno.

### Refresh tokens

- **No se implementan día uno.** F2 §6.3 no contempla `/auth/refresh`; el
  `JWT_REFRESH_TOKEN_EXPIRE_DAYS` heredado del esqueleto queda como código
  muerto (lo eliminaré como limpieza posterior).
- Cuando el `access_token` expira (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, hoy
  15 min), el frontend dispara un re-login con Google. Como Google Identity
  Services mantiene su propia sesión en el navegador del usuario, esto es
  típicamente silencioso (sin volver a introducir contraseña).
- El frontend puede subir el TTL del backend cambiando la variable de entorno
  sin tocar código.

### `/auth/logout`

- Como los JWT son stateless, el endpoint día uno devuelve `204` si el
  bearer es válido y `401` si no — pero **no invalida nada server-side**.
  El cliente borra su token de memoria. Si se rotara JWT_SECRET, todos los
  tokens vivos quedarían invalidados, que es la única "invalidación masiva"
  disponible sin BBDD/Redis de blacklist.

## Alternativas descartadas

- **Cookies HTTPOnly + CSRF token** — más seguras frente a XSS pero
  complican el desarrollo (CORS con `credentials: 'include'`, CSRF tokens
  emparejados, dominio compartido en producción). F2 explícitamente lo deja
  abierto; bearer es el camino corto.
- **Refresh tokens con tabla `refresh_tokens` día uno** — añade una tabla
  no contemplada por F2 §5 y un endpoint no contemplado por F2 §6.3. Se
  podría justificar en una pieza posterior si la experiencia de
  re-login-cada-15-min molesta a usuarios reales.
- **Blacklist en Redis** — requiere Redis activo para validar cada bearer
  (overhead) y solo aporta capacidad de logout server-side. Día uno F2 no
  lo exige.

## Consecuencias

**Más fácil:**
- Implementación minimal: el endpoint emite un JWT, las dependencias FastAPI
  decodifican el `Authorization: Bearer ...`. Cero tablas nuevas.
- Frontend puede usar cualquier patrón de almacenamiento (memoria,
  sessionStorage); no depende del backend.

**Más difícil:**
- No hay logout server-side real. Mitigación: el TTL corto del JWT es la
  ventana de exposición máxima si el token se filtra.
- Re-login frecuente (cada 15 min) puede sentirse engorroso. Mitigación:
  si en uso real molesta, esta ADR queda sucedida por otra que añada
  refresh tokens.

**Deuda asumida:**
- Cuando se quiera revocar sesiones individuales (p.ej. "cerrar sesión en
  todos los dispositivos") será necesario añadir blacklist o refresh
  tokens. Está fuera de alcance día uno.

## Cambios concretos derivados

- Endpoint `POST /api/v1/auth/google` devuelve
  `{access_token, token_type: "bearer", expires_in, user}` en JSON.
- Endpoint `POST /api/v1/auth/logout` valida bearer y devuelve `204` o `401`.
- Endpoint `GET /api/v1/auth/me` valida bearer y devuelve el `User` actual.
- Dependencia FastAPI `get_current_user` extrae el bearer, decodifica y
  busca el `User`.
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS` y `create_refresh_token()` quedan sin uso
  (eliminables en una limpieza menor más adelante).
