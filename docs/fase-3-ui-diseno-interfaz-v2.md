# Documento de Planificación UI — Diseño de la Interfaz

**Producto:** Webapp de soporte a un screening de empresas de bolsa (USA / NASDAQ)
**Fase:** UI / Diseño de la interfaz (consolidado de la fase completa)
**Estado:** Diseño consolidado, **revisado tras auditoría de diseño (CTO)**. No se ha escrito código (pseudocódigo y wireframes esquemáticos solo para ilustrar). Marco dentro del cual encajará la construcción del frontend.
**Entrada heredada:** Definición de Funcionalidades (F0), Decisiones de Arquitectura (F1), Planificación de Servidor y Datos (F2).
**Base de componentes:** shadcn/ui sobre Radix + Tailwind.
**Historial:** v1 consolidación del diseño de UI; **v2 incorpora las correcciones de la auditoría de diseño del CTO (ver sección 12).**

---

## Cómo leer este documento

Continúa la disciplina de etiquetado de las fases anteriores. Cada elemento se marca como una de tres cosas:

- **[Heredada]** — decisión de negocio, arquitectura o contrato que viene de F0/F1/F2 y que esta fase respeta sin redecidir.
- **[Diseño UI]** — decisión de diseño de interfaz tomada en esta fase.
- **[Realimentación F2]** — hallazgo de diseño de UI que toca un contrato de la Fase 2 (cerrada); queda registrado para validación de quien posee F2, **no se aplica unilateralmente**.

Los bloques modificados por la auditoría del CTO se marcan en línea con **【REV-CTO: Cn/In/Mn】**, referidos al hallazgo de origen. La sección 12 mapea cada hallazgo a dónde se resolvió.

Esta fase **diseña la interfaz; no construye**. Todo lo marcado como acción o realimentación pertenece a la construcción o a una revisión de F2.

El documento recorre seis bloques, en el orden en que se decidieron, cada uno apoyándose en el anterior: (1) arquitectura de UI a alto nivel; (2) base de componentes; (3) jerarquía de componentes; (4) contratos de los componentes base; (5) catálogo de estados; (6) flujo de estado y consumo de API; y los criterios transversales de responsive y accesibilidad. Cierra con el registro de decisiones, las realimentaciones y el changelog de la auditoría.

---

## 0. Decisiones heredadas que esta fase trata como cerradas

Para no reabrir lo decidido, se listan las decisiones de fases anteriores que gobiernan toda la fase de UI:

- **Renderizado:** SPA servida tras autenticación; el backend sirve JSON, toda la presentación vive en el frontend; frontera limpia SPA↔API. Sin SEO ni parte pública. (F1 §3) **[Heredada]**
- **Stack frontend:** React como SPA. (F1 §4.1) **[Heredada]**
- **API:** REST bajo `/api/v1`; error uniforme `{error:{code,message,details}}`; fechas ISO-8601, timestamps UTC con `Z`, fechas de calendario `YYYY-MM-DD`; paginación `limit`+`cursor` opaco; autorización comprobada en backend. (F2 §6.1) **[Heredada]**
- **Asincronismo:** crear un backtest devuelve `202 + pending`; el cliente hace **polling** hasta estado terminal; no hay endpoint que ejecute y espere. (F2 §6.5) **[Heredada]**
- **Roles / capacidades:** dos capacidades efectivas día uno — `viewer` (lee todo) y `analyst` (además crea/cancela backtests); `admin` reservado sin capacidades, no se asigna. (F2 §5.1) **[Heredada]**
- **Reglas de negocio firmes día uno:** equiponderación 1/N; reporte en USD; backtests inmutables (sin DELETE, con CANCEL). (F0, F2 §5.2/§6.5) **[Heredada]**
- **Datos significativos:** los `null` del screening son explícitos (dato ausente real en origen), no ceros ni vacíos. (F2 §6.4) **[Heredada]**

---

## 1. Arquitectura de UI a alto nivel

### 1.1 Reparto por renderizado

La app es una SPA tras login, sin SEO ni parte pública (F1 §3, F0). Esto colapsa el reparto público/privado a su forma mínima: **prácticamente todo es privado y no indexable.** La única frontera real no es público/privado sino **autenticado / no autenticado**.

| Zona | Acceso | Indexable | Qué contiene |
|---|---|---|---|
| Zona pública mínima | Sin sesión | No (`noindex` deliberado) | Solo login y pantallas de error de acceso |
| Zona de aplicación | Con sesión válida | No | Todo lo demás: visor, backtests, administración futura |

Como es SPA, el reparto **no se traduce en estrategias de renderizado distintas** (todo se renderiza en cliente), sino en **un guardián de rutas** que separa lo alcanzable sin sesión de lo que la exige. Esa es toda la consecuencia del renderizado sobre el enrutado. **[Diseño UI]**

### 1.2 Zonas de la app

- **Zona de Acceso** — entrar. Login con Google y estados de "no puedes entrar". Única zona alcanzable sin sesión. **[Heredada]**
- **Zona de Visor** — consultar el análisis. Mapa histórico, ficha de empresa, y (pospuestos) panel de situación y resumen semanal. **[Heredada]**
- **Zona de Backtesting** — validar decisiones. Lanzar, ver resultado con contraste contra benchmarks, y (pospuesto) comparar. **[Heredada]**
- **Zona de Administración** — gestión de invitados/roles. **Pospuesta** (alta manual día uno); hueco previsto en el enrutado, sin vistas día uno. **[Heredada]**

### 1.3 Inventario de vistas

Cada vista con su prioridad de F0 y los endpoints de F2 que consume. Las pospuestas se enumeran pero no se desarrollan.

**Zona de Acceso**

- **V-LOGIN — Entrada / Login.** Día uno. Inicia el flujo de Google. Consume `POST /auth/google`. **[Heredada]**
- **V-ACCESO-DENEGADO — Acceso no autorizado.** Día uno. Estado diferenciado para `403 user_not_authorized` ("tu email no está en la lista"; el alta es manual). Distinto de un fallo de credenciales. **[Heredada + Diseño UI]**

**Zona de Visor**

- **V-MATRIX — Mapa histórico de selección.** Día uno. Corazón del visor. Cuadrícula empresa × semana, ventana de semanas navegable (~26 recientes por defecto, hacia atrás hasta ~3 años). Cada celda: no estuvo / estuvo en universo / fue seleccionada. Consume el endpoint de matriz pendiente (R1) y subsidiariamente `GET /weeks`. **[Heredada (función) + Realimentación F2 (endpoint)]**
- **V-COMPANY — Ficha de empresa por semana.** Día uno. Métricas, cualitativos LLM, por qué se seleccionó o no. "Mapa + ficha son el visor mínimo usable" (F0). Consume `GET /weeks/{week_date}/companies/{ticker}`. **【REV-CTO: C1 — el catálogo concreto de campos de la ficha NO está definido en el contrato de F2; ver R2-bis. Esta vista se diseña a nivel de estructura y estados, no de campos concretos, que quedan pendientes de realimentación.】** **[Heredada]**
- **V-PANEL — Panel de situación.** *Pospuesta.* Consumiría `GET /weeks`. **[Heredada]**
- **V-RESUMEN-SEMANA — Resumen de la selección semanal.** *Pospuesta.* **[Heredada]**

**Zona de Backtesting**

- **V-BT-LISTA — Lista de backtests.** Día uno. Espacio compartido (todos ven los de todos). Consume `GET /backtests`. **[Heredada]**
- **V-BT-LANZAR — Lanzar un backtest.** Día uno. Formulario de parámetros (1/N y USD fijos). Solo `analyst`. Consume `POST /backtests` (202). **[Heredada]**
- **V-BT-RESULTADO — Resultado de un backtest.** Día uno. Métricas, curva de capital, drawdowns y contraste contra benchmarks en la misma pantalla. Maneja los estados asíncronos por polling. Consume `GET /backtests/{id}` (polling), `/result`, `/snapshot`. **[Heredada]**
- **V-BT-COMPARAR — Comparar backtests.** *Pospuesta.* Costura **verificada**, no solo afirmada (ver §1.5). **【REV-CTO: C2】** **[Heredada]**

**Zona de Administración**

- **V-ADMIN-INVITADOS — Gestión de invitados y permisos.** *Pospuesta.* Hueco previsto en el enrutado. **[Heredada]**

### 1.4 Enrutado y navegación

Árbol de rutas (wireframe esquemático, no código):

```
/  (raíz)
│
├─ /login                         V-LOGIN            [sin sesión]
├─ /sin-acceso                    V-ACCESO-DENEGADO  [sin sesión]
│
└─ (guardián de sesión) ──────────────────────────── [exige sesión]
   │
   ├─ /                           → redirige a /mapa (entrada por defecto)
   │
   ├─ /mapa                       V-MATRIX           [día uno]
   ├─ /mapa/:semana/:ticker       V-COMPANY          [día uno]
   │
   ├─ /backtests                  V-BT-LISTA         [día uno]
   ├─ /backtests/nuevo            V-BT-LANZAR        [día uno, solo analyst]
   ├─ /backtests/:id              V-BT-RESULTADO     [día uno]
   ├─ /backtests/comparar         V-BT-COMPARAR      [pospuesta — ruta prevista] 【REV-CTO: C2】
   │
   ├─ /panel                      V-PANEL            [pospuesta — hueco]
   ├─ /admin                      V-ADMIN-INVITADOS  [pospuesta — hueco]
   │
   └─ *  (cualquier otra)         → vista 404 interna
```

Decisiones del árbol:

- **Entrada por defecto = `/mapa`.** El visor es el corazón de la app y lo ven los tres roles. La entrada no es un dashboard, es el mapa. **[Diseño UI]**
- **La ficha de empresa es ruta anidada y direccionable** (`/mapa/:semana/:ticker`). Se abre desde una celda; su contexto es siempre "esta empresa, esta semana". `:semana` es la `week_date` canónica (lunes NY, `YYYY-MM-DD`). Si además es panel o vista completa se decide en el detalle visual; aquí solo se fija que es direccionable. **[Diseño UI]**
- **`/backtests/nuevo` es ruta propia, no modal.** El formulario tiene entidad y conviene que sea enlazable. **[Diseño UI]**
- **`/backtests/:id` (UUID) sirve los tres estados** asíncronos; el estado lo resuelve la vista por polling, no hay rutas distintas por estado. **[Diseño UI, deriva del contrato asíncrono Heredado]**
- **`/backtests/comparar` es ruta prevista** (no construida) para que comparar sea enchufable; ver la verificación de costura en §1.5. **【REV-CTO: C2】** **[Diseño UI]**

**El guardián de rutas** (pseudo-flujo):

```
¿Hay sesión válida? (se resuelve con GET /auth/me)
─ No  → redirigir a /login (guardando el destino para volver tras entrar)
─ Sí  → ¿La ruta exige una capacidad concreta?
         ─ /backtests/nuevo exige rol analyst
            ─ viewer → no se muestra la ruta; si la teclea, vista "sin permiso"
         ─ resto de rutas con sesión → permitir
```

Dos principios heredados que respeta: la ocultación es cosmética y la autorización es del backend (F1 §5); `GET /auth/me` es la fuente de verdad de sesión y rol, y el guardián es agnóstico al transporte de sesión (cookie vs token, detalle de construcción de F2). **[Heredada + Diseño UI]**

**Frontera guardián ↔ RoleGate (aclaración).** El **guardián de rutas** decide el acceso a **rutas completas** (te deja entrar a `/backtests/nuevo` o no). El componente **`RoleGate`** (§3.3) oculta **elementos dentro de una vista ya permitida** (p.ej. el botón "Lanzar" dentro de `/backtests`). No se solapan: uno gobierna navegación, el otro elementos. Ambos son cosméticos; la autorización real está en backend. **【REV-CTO: M1】** **[Diseño UI]**

**Navegación persistente:** da acceso a Visor (Mapa) y Backtests, más identidad y salir (`POST /auth/logout`). Administración aparecerá aquí condicionada al rol cuando se construya. **[Diseño UI]**

### 1.5 Verificación de la costura "comparar backtests" 【REV-CTO: C2】

F1 §9.7 exige que comparar backtests sea posible después sin rediseñar. El documento v1 lo declaraba "costura" sin respaldo. Aquí se **verifica** qué hace esa costura enchufable, sin diseñar la vista:

1. **Ruta prevista:** `/backtests/comparar?ids=a,b,c` (registrada en §1.4).
2. **`EquityChart` admite N series desde su contrato** (no una cartera + un benchmark cableados): ver §4.2 (contrato de charts). Esto es lo que evita que comparar sea un rediseño del chart. **Es el punto crítico de la costura.**
3. **`MetricsPanel` debe poder renderizarse en columnas comparativas** (una por backtest), no asumir un único backtest. Su contrato (§4.2) lo refleja.
4. **Dato disponible:** cada backtest persiste sus parámetros y resultado (F2 §5.2; F1 §9.7), así que comparar es leer N backtests ya completados y superponer/yuxtaponer — no requiere endpoint nuevo día uno (se piden N `GET /backtests/{id}/result`).

Con estos cuatro puntos, comparar queda como **enchufar una vista** sobre componentes ya capaces, no como rediseño. La aridad-N de los charts (punto 2) se decide ahora porque es barata de prever y carísima de retrofitear. **[Diseño UI, verifica F1 §9.7]**

---

## 2. Base de componentes

**Decisión: shadcn/ui sobre Radix + Tailwind.** **[Diseño UI]**

Encuadre: herramienta interna, grupo cerrado, sin SEO, escala pequeña, mantenible por una persona, un idioma. El peso visual recae en dos piezas densas de datos (la matriz empresa × semana y los gráficos de backtest) que **ninguna librería regala** y que se construyen o integran aparte en cualquier escenario. Por eso la base se elige para minimizar fricción en el andamiaje (navegación, formularios, diálogos, tablas simples) y maximizar control en las piezas difíciles, no por tamaño de catálogo.

Comparativa que sustentó la decisión:

| Opción | Velocidad | Control de diseño | Accesibilidad base | Peso | Mantenimiento a largo plazo |
|---|---|---|---|---|---|
| Sistema propio desde cero | La más baja | Total | La que más sufre (primitivos accesibles son trabajo experto) | Mínimo | Recae entero en una persona; desproporcionado |
| MUI (baterías incluidas) | La más alta | Bajo (muy opinado; pelear contra Material) | Decente | Alto (motor de estilos + bundle grande) | Migraciones de versión costosas; no resuelve matriz ni charts |
| **shadcn/Radix (elegida)** | Media (ensamblar, no recibir pintado) | Alto (estilo propio) | Sólida (Radix resuelve lo difícil) | Ajustado (solo entra lo que se usa) | Posees el código (sin gran migración); posees también sus bugs |

**Por qué la elegida:** da la accesibilidad difícil ya resuelta (lo único de la opción propia que de verdad duele), control real sobre el diseño para pantallas densas, y peso/mantenimiento acordes a "una persona, escala pequeña, 5 años". El precio —ensamblar en vez de recibir pintado— es asumible sin presión de time-to-market público.

**Alternativas descartadas:** sistema propio (desproporcionado para el perfil); MUI (estética impuesta y peso, sin resolver las piezas difíciles).

### 2.1 Librería de gráficos — decisión registrada 【REV-CTO: M5】

Los charts de backtest (`EquityChart`, `DrawdownChart`) son una de las tres piezas difíciles y la librería que los sostiene es una decisión de 5 años (migrar de librería de charts es caro). Se registra con el mismo rigor que la base de componentes.

**Decisión: recharts.** **[Diseño UI]**

**Porqué:** es declarativa y nativa de React (componentes, no un canvas imperativo que envolver), integra bien con el modelo de props/estado de los estratos, cubre de sobra curvas de equity y drawdowns con múltiples series, y su peso es razonable a esta escala. Encaja con el stack sin fricción.

**Alternativas descartadas:**
- **visx** — más potente y flexible (primitivos de bajo nivel sobre D3), pero exige construir más a mano; desproporcionado para curvas estándar y una persona de mantenimiento.
- **nivo** — bonito y completo, pero más pesado y opinado estéticamente de lo necesario.
- **Chart.js** (vía wrapper) — imperativo sobre canvas, encaja peor con el modelo declarativo de React y con la composición por props que pide la aridad-N.

**Tradeoff asumido:** recharts es SVG, lo que a volúmenes enormes de puntos rinde peor que canvas; a la magnitud de este producto (curvas de decenas a pocos cientos de puntos por serie) es irrelevante. Si algún día una curva tuviera decenas de miles de puntos, la librería de charts es una costura sustituible tras el contrato de props de §4.2. **[Diseño UI]**

---

## 3. Jerarquía de componentes

### 3.1 Los cuatro estratos

La regla que separa los estratos: **cuánto sabe el componente sobre el dominio y sobre el servidor.** Cuanto más arriba, más tonto y reutilizable; cuanto más abajo, más sabe.

```
Estrato 1 — PRIMITIVOS (shadcn/Radix)        no saben nada: ni dominio ni servidor
Estrato 2 — COMPONENTES BASE                 saben de patrones de UI, no de dominio
Estrato 3 — COMPONENTES DE DOMINIO           saben de screening/backtest, no de la API
Estrato 4 — VISTAS (composición + datos)     saben de la API y orquestan todo
```

**La frontera dura es 3↔4:** el dato de servidor (hooks que llaman a la API, polling, cursores) vive **solo en el estrato 4**. Los estratos 1–3 reciben datos por props y emiten eventos hacia arriba; no conocen `fetch`, ni la capa de datos, ni endpoints. Esto hace los componentes testeables en aislamiento y reutilizables. **[Diseño UI]**

### 3.2 Dónde vive el estado (resumen; se detalla en §6)

- **Dato de servidor** (screening, backtests, sesión): capa de datos, en hooks por vista (estrato 4). Allí viven polling, cursores y cache. **[Diseño UI]**
- **Estado de UI local** (celda activa, panel abierto, valores de form antes de enviar): en el componente que lo posee, lo más abajo posible. **Excepción registrada:** el estado de UI que *parametriza una petición al servidor* (la ventana de semanas de la matriz) **no es local del componente**, sube a la vista; ver §6.1 e I3. **【REV-CTO: I3】**
- **Estado global de cliente** (identidad/rol de `GET /auth/me`): un contexto único, leído por guardián y navegación. La autorización real sigue en backend. **[Heredada]**

### 3.3 Árbol de composición

**Estrato 1 — Primitivos (shadcn/Radix, copiados al repositorio):** Button, Input, Select, Combobox, Dialog, Popover, Tooltip, DropdownMenu, Tabs, Checkbox, RadioGroup, **Toast** (uso asignado: confirmaciones de mutación y errores transitorios; ver nota), Skeleton, Table (simple), ScrollArea, Separator, Badge, Avatar. Accesibilidad/foco/teclado de Radix; estilo por tokens Tailwind.

**Uso de `Toast` 【REV-CTO: M4】:** confirmaciones no bloqueantes de mutación (backtest lanzado → "Backtest en cola"; backtest cancelado → "Cancelado") y errores transitorios que no justifican una pantalla de error (p.ej. un fallo de red puntual durante el polling que se recupera). No se usa para errores que tienen su propio estado de vista (esos van a `ErrorState`). **[Diseño UI]**

**Estrato 2 — Componentes base reutilizables (patrones, sin dominio):**

```
├─ AppShell                 layout: navegación persistente + área de contenido
│   ├─ NavBar
│   └─ ContentArea
├─ DataState<T>             envuelve los 4 estados de carga (pieza clave)
├─ DataTable                tabla genérica: orden, cursor, fila clicable
├─ FormField                label + control + error + ayuda
├─ PageHeader               título + acciones de cabecera
├─ EmptyState               "no hay nada aquí"
├─ ErrorState               error con código + reintento
├─ ConfirmDialog            confirmación genérica
└─ CursorPager              "cargar más" sobre cursor opaco
```

`DataState<T>` es la pieza más importante del estrato: estandariza cargando/vacío/error/ok una sola vez; concentra ahí la robustez ante datos ausentes/erróneos. `CursorPager` encapsula el cursor opaco; el resto de la app nunca lo toca a mano. **[Diseño UI, deriva de F2 §6.1/§6.4]**

**Estrato 3 — Componentes de dominio (vocabulario del producto; no llaman a la API):**

```
├─ Screening
│   ├─ SelectionMatrix          cuadrícula empresa × semana (pieza difícil nº1)
│   │     ├─ MatrixWeekHeader    eje semanas, scroll horizontal
│   │     ├─ MatrixCompanyRow    eje empresa, sticky
│   │     └─ MatrixCell          estado: no estuvo / universo / seleccionada / sin dato
│   ├─ CompanyMetrics            métricas cuantitativas (null explícito) — contrato pendiente de R2-bis
│   ├─ CompanyQualitative        cualitativos LLM — contrato pendiente de R2-bis
│   ├─ WeekBadge                 representa una Week
│   ├─ TickerLabel               símbolo + nombre + país/divisa
│   └─ RoleGate                  muestra/oculta según rol (cosmético)
│
└─ Backtesting
    ├─ BacktestStatusBadge       pending/running/completed/failed/cancelled
    ├─ BacktestProgress          progreso honesto por semanas (no %)
    ├─ BacktestParamsForm        parámetros (1/N y USD fijos)
    ├─ EquityChart               curva(s) cartera vs benchmark (pieza difícil nº2; N series)
    ├─ DrawdownChart             drawdowns (N series)
    ├─ MetricsPanel              métricas núcleo (renderizable en columnas comparativas)
    ├─ BenchmarkContrast         contraste cartera vs benchmark
    └─ SnapshotViewer            snapshot congelado (auditoría)
```

`SelectionMatrix` y los charts son las piezas que ninguna librería da; son componentes de dominio de primer nivel (la matriz no es una `DataTable`). A la magnitud confirmada (decenas de empresas × 26–150 semanas) no necesitan virtualización agresiva día uno; queda como costura si el universo crece. `BacktestProgress` muestra semanas, no un % inventado. `BacktestParamsForm` no expone otra divisa ni otra ponderación. `RoleGate` es explícitamente cosmético: la autorización vive en backend.

**Nota sobre el contrato del estrato 3 【REV-CTO: I1, C1】:** los charts (`EquityChart`/`DrawdownChart`) y `MetricsPanel` **sí tienen contrato cerrado en §4.2**, porque su dependencia (la forma de la curva de equity, F2 §5.2, y la aridad-N de §1.5) está definida y no depende de R2. En cambio `CompanyMetrics`/`CompanyQualitative` **quedan con contrato pendiente** porque dependen del catálogo de campos de la ficha, que es realimentación abierta (R2-bis). La distinción es deliberada: se cierra lo que se puede cerrar, se aplaza solo lo que de verdad depende de un contrato abierto. **[Diseño UI]**

**Estrato 4 — Vistas (único estrato que toca la API):**

```
VISTA                          orquesta                          endpoints F2
├─ LoginView                   FormField                         POST /auth/google
├─ AccessDeniedView            ErrorState                        (resultado de auth)
├─ MatrixView (/mapa)          DataState › SelectionMatrix       [R1] + GET /weeks
│                              (posee la ventana de semanas)
├─ CompanyView (/mapa/:s/:t)   DataState › CompanyMetrics +      GET /weeks/{s}/companies/{t}
│                              CompanyQualitative + TickerLabel
├─ BacktestListView            DataState › DataTable +           GET /backtests
│                              CursorPager + BacktestStatusBadge
├─ BacktestNewView (/nuevo)    BacktestParamsForm (RoleGate)     POST /backtests → 202
├─ BacktestResultView (/:id)   DataState (polling) ›             GET /backtests/{id} (poll)
│                              BacktestProgress | resultado       /result, /snapshot
└─ NotFoundView (*)            EmptyState
```

`BacktestResultView` es la más compleja: una sola ruta resuelve los tres estados asíncronos por polling. El polling vive en esta vista, no más abajo. **[Heredada + Diseño UI]**

### 3.4 Organización en el repositorio

```
src/
├─ app/              estado de arranque (resolución de sesión, shell global) 【REV-CTO: I5】
├─ components/
│   ├─ ui/            Estrato 1 — primitivos shadcn (copiados)
│   └─ base/          Estrato 2 — DataState, DataTable, FormField, ...
├─ domain/
│   ├─ screening/     Estrato 3 — SelectionMatrix, CompanyMetrics, ...
│   └─ backtesting/   Estrato 3 — EquityChart, BacktestProgress, ...
├─ views/             Estrato 4 — una carpeta por vista (vista + sus hooks de datos)
├─ lib/               cliente API, configuración de la capa de datos, tokens, mapa de invalidación
└─ routes/            árbol de rutas + guardián
```

**Regla de oro:** un componente solo importa de su estrato o de los de encima, nunca de los de debajo. Una vista importa dominio/base/primitivos; un dominio importa base/primitivos pero nunca una vista; un base nunca importa dominio. Hace estructuralmente imposible contaminar de dominio un componente reutilizable. **[Diseño UI]**

---

## 4. Contratos de los componentes base (estrato 2) y de las piezas de dominio cerrables

Equivalente en UI a los contratos de API: el acuerdo de cómo se usa cada componente, definido antes de construirlo. Notación al estilo TypeScript (especificación, no implementación).

### 4.1 Convenciones del contrato

- **Obligatoria vs opcional:** `?` marca opcional; sin `?` es obligatoria.
- **Eventos:** prefijo `on*`, reciben el dato ya útil, no el evento DOM crudo.
- **Variantes:** enumeradas y cerradas, nunca strings libres.
- **Genéricos:** los componentes de datos son genéricos en `<T>`; no conocen el dominio.
- **Composición sobre configuración:** contenido arbitrario por `children`/render-prop, no por props de configuración que intenten preverlo todo.
- **Accesibilidad heredada:** al envolver Radix no se pierden etiquetas/descripciones/asociaciones.

### 4.2 Contratos

**`DataState<T>` — el más importante**

```
DataState<T> {
  status:       "loading" | "empty" | "error" | "ready"   // obligatoria
  data?:        T                      // presente sólo si status==="ready"
  error?:       ApiError               // presente sólo si status==="error"
  children:     (data: T) => ReactNode // render del caso "ready"; obligatoria
  loadingSlot?: ReactNode              // default: <Skeleton/>
  emptySlot?:   ReactNode              // default: <EmptyState/>
  errorSlot?:   (error: ApiError, retry: () => void) => ReactNode
  onRetry?:     () => void
}
ApiError { code: string; message: string; details?: object | null }
```

Decisiones: `status` explícito, no derivado de `data == null` (los null de F2 son significativos); caso "ready" como render-prop (garantiza por tipos el acceso seguro a `data`); el reintento es parte del contrato del error; **no** maneja el estado asíncrono del backtest (eso es dominio, lo lleva `BacktestProgress`). **[Diseño UI, deriva de F2 §6.4]**

**`DataTable<T>`**

```
DataTable<T> {
  columns:       ColumnDef<T>[]        // obligatoria
  rows:          T[]                   // obligatoria; ya cargadas
  rowKey:        (row: T) => string    // obligatoria
  onRowClick?:   (row: T) => void
  sort?:         SortState             // ver nota REV-CTO I4
  onSortChange?: (sort: SortState) => void
  isLoading?:    boolean
  emptySlot?:    ReactNode
}
ColumnDef<T> { id; header: ReactNode; cell: (row: T) => ReactNode;
               sortable?: boolean; align?: "start" | "end"; width?: string }
SortState { columnId: string; direction: "asc" | "desc" }
```

No pagina ni ordena por su cuenta: recibe `rows` cargadas y emite `onSortChange`; el orden y la página son decisiones de servidor (cursor opaco). Sirve para la lista de backtests; **no** para la matriz.

**Ordenación en la lista de backtests 【REV-CTO: I4】:** `GET /backtests` (F2 §6.5) ofrece **solo** orden por recencia vía cursor opaco `(created_at, id)`; el contrato **no** soporta ordenar por columna arbitraria. Decisión: **día uno la lista de backtests NO es ordenable por columna** — todas sus columnas se usan con `sortable: false`. La capacidad de orden de `DataTable` se conserva en el contrato para otros usos futuros, pero **no se promete en esta vista lo que el backend no da**. Si más adelante se quiere ordenar por columna, es realimentación a F2 (parámetro de orden en `GET /backtests`), no algo que el front resuelva por su cuenta. **[Diseño UI, deriva de F2 §6.5]**

**`CursorPager`**

```
CursorPager {
  hasMore:        boolean              // obligatoria
  isLoadingMore?: boolean
  onLoadMore:     () => void           // obligatoria
  // NO expone el cursor: es opaco y vive en la vista
}
```

Patrón "cargar más", nunca ve el cursor (opaco, vive en el hook de la vista). **[Diseño UI, deriva de F2 §6.1]**

**`FormField`**

```
FormField {
  label:     string                    // obligatoria (accesibilidad)
  htmlFor:   string                    // obligatoria; liga label↔control
  children:  ReactNode                 // el control; obligatoria
  error?:    string
  hint?:     string
  required?: boolean
}
```

`label`/`htmlFor` obligatorias para no perder la asociación ni el anuncio del error al envolver Radix (`aria-describedby` se cablea aquí). **[Diseño UI]**

**`AppShell` + `NavBar`**

```
AppShell { children: ReactNode }       // navegación fija; su contenido lo decide AppShell
NavBar {
  user:     SessionUser                // obligatoria; de GET /auth/me
  items:    NavItem[]                  // obligatoria; YA filtrados por rol
  onLogout: () => void                 // obligatoria; → POST /auth/logout
}
NavItem { label: string; to: string }
SessionUser { fullName?: string; email: string; role: Role }
Role = "viewer" | "analyst" | "admin"  // admin reservado
```

`NavBar` recibe `items` ya filtrados por rol; no filtra ella. **[Heredada + Diseño UI]**

**`EmptyState` y `ErrorState`**

```
EmptyState { title: string; description?: string;
             action?: { label: string; onAction: () => void } }
ErrorState { error: ApiError; onRetry?: () => void }
```

`ErrorState` muestra `message` mapeado desde `code` a texto legible; **no** muestra `details` ni el `context` del error (eso es para logs). Cara visible de `analysis_schema_mismatch`, etc. **[Diseño UI, deriva de F2 §6.6]**

**`ConfirmDialog`**

```
ConfirmDialog {
  open:         boolean                // obligatoria; controlado
  onOpenChange: (open: boolean) => void// obligatoria
  title:        string                 // obligatoria
  description?: string
  confirmLabel?: string
  onConfirm:    () => void             // obligatoria
  variant?:     "default" | "destructive"
  isPending?:   boolean
}
```

Controlado (no autónomo). `destructive` cubre la cancelación de backtest (cancelable pero no borrable, F2 I3). **[Diseño UI, deriva de F2 §6.5]**

**`Button` y `PageHeader`**

```
Button { variant?: "primary" | "secondary" | "ghost" | "destructive";
         size?: "sm" | "md" | "lg"; isLoading?: boolean; disabled?: boolean;
         children: ReactNode }
PageHeader { title: string; actions?: ReactNode }
```

`isLoading` implica `disabled`. **[Diseño UI]**

### 4.3 Contratos de las piezas de dominio cerrables 【REV-CTO: I1, C2】

Estos componentes **no dependen de R2** (su forma de dato está definida en F2 §5.2 y en la verificación de §1.5), por lo que se cierran ahora en vez de aplazarse con el resto del estrato 3.

**`EquityChart` — admite N series (clave para comparar, §1.5)**

```
EquityChart {
  series:      EquitySeries[]          // obligatoria; N series, NO una cartera+un benchmark cableados
  height?:     number
  showLegend?: boolean                 // default true
}
EquitySeries {
  id:     string                       // identidad de la serie (p.ej. backtest id, o "benchmark")
  label:  string                       // nombre legible en la leyenda
  points: { date: string; value: number }[]   // date = YYYY-MM-DD (F2 §6.1); value en USD
  role?:  "portfolio" | "benchmark"    // para estilo distinto; opcional
}
```

**Decisión clave:** `series` es una lista de longitud arbitraria. Día uno se le pasan dos (cartera + benchmark); para comparar (§1.5) se le pasan N. **El componente no cambia entre ambos casos.** Esto es lo que convierte "comparar" en costura enchufable y no en rediseño. La forma del punto sigue F2 §5.2 (`point_date`, `value`) y §6.1 (fecha `YYYY-MM-DD`). **[Diseño UI, deriva de F2 §5.2 y verifica F1 §9.7]**

**`DrawdownChart`** — mismo contrato de `series` (N), `value` expresado como caída relativa. **[Diseño UI]**

**`MetricsPanel` — renderizable en columnas comparativas**

```
MetricsPanel {
  columns: MetricsColumn[]             // obligatoria; 1 columna día uno, N al comparar
}
MetricsColumn {
  id:      string                      // backtest id (o "benchmark")
  label:   string
  metrics: { totalReturn; cagr; volatility; sharpe; maxDrawdown; extra?: object }
           // métricas núcleo de F2 §5.2 (backtest_result); extra = metrics_extra
}
```

**Decisión:** `columns` es lista, no un único objeto de métricas. Una columna día uno; N columnas yuxtapuestas al comparar, sin rediseño. Las métricas núcleo son las de `backtest_result` (F2 §5.2). **[Diseño UI, deriva de F2 §5.2 y verifica F1 §9.7]**

**`BacktestProgress`, `BacktestStatusBadge`, `SelectionMatrix`** — su contrato detallado de props depende de la forma exacta de las respuestas (progreso de F2 §6.5, ya definida; matriz de R1, **no confirmada**). El de progreso y badge se puede cerrar; el de `SelectionMatrix` espera a R1. Se documentan sus estados en §5; el contrato de props fino se cierra al confirmar R1. **[Diseño UI / Realimentación F2 para la matriz]**

### 4.4 Tipos compartidos (definidos una vez, como esquemas de OpenAPI)

```
ApiError    { code, message, details? }       // F2 §6.1
Role        "viewer" | "analyst" | "admin"     // F2 §5.1
SessionUser { fullName?, email, role }          // GET /auth/me
```

### 4.5 Dos principios que gobiernan los contratos

- **Componentes controlados, no autónomos.** Lo que tiene estado relevante (sort, apertura de diálogo, paginación) recibe el estado y emite el cambio; no lo guarda dentro. Evita una segunda fuente de verdad. **[Diseño UI]**
- **Datos por props, eventos hacia arriba; nadie de aquí llama a la API.** Respeta la frontera 3↔4. **[Diseño UI]**

---

## 5. Catálogo de estados

Artefacto que evita que la construcción solo programe el camino feliz.

### 5.1 Vocabulario de estados

- **Nominal** — camino feliz, dato presente y correcto.
- **Carga** — *inicial* (no hay nada → esqueleto) vs *recarga* (ya hay dato → overlay sutil, sin parpadeo).
- **Vacío** — petición correcta sin datos. Distinto de error y de carga.
- **Error** — por código HTTP (ver tabla).
- **Parcial / dato ausente** — campos `null` significativos (F2 §6.4); no es error.

Tratamiento por código, decidido una vez:

| Código | Qué pasó | Qué hace la UI |
|---|---|---|
| 401 | Sesión caída/ausente | Redirige a `/login` guardando destino; sin error rojo |
| 403 | Rol insuficiente | "No tienes permiso"; sin reintento |
| 404 | No existe | Vista "no encontrado" del recurso |
| 409 | Conflicto de estado | Caso especial backtest; no es error de usuario |
| 422 | Regla de negocio | Error junto al campo que lo causó |
| 502/503 | Dependencia externa caída | "Servicio no disponible ahora"; reintento |
| 500 | Fallo propio (incl. schema_mismatch) | Mensaje legible desde `code`; reintento; nunca volcado crudo |

**[Diseño UI, deriva de F2 §6.1/§6.6]**

### 5.2 Estado de arranque de la app (global, entre vistas) 【REV-CTO: I5】

Antes de cualquier vista, la SPA debe resolver si hay sesión (`GET /auth/me`). El momento entre el arranque y esa resolución es un estado global, distinto del estado de cada vista, y el más olvidado de toda SPA.

| Estado de arranque | Qué pasa | Qué se muestra |
|---|---|---|
| Resolviendo sesión | `GET /auth/me` en vuelo al cargar la app | **Shell mínimo / splash** (logo + esqueleto de layout), nunca pantalla en blanco ni flash de login |
| Sesión válida | `/auth/me` → 200 | Monta la zona de aplicación en la ruta destino (o `/mapa`) |
| Sin sesión | `/auth/me` → 401 | Redirige a `/login` |
| `/auth/me` falla (red/500) | Error no-401 | Pantalla de error de arranque con reintento (no asume "sin sesión") |

Esto elimina el *flash* de login (mostrar login un instante antes de saber que sí había sesión) y el *flash* en blanco. Vive en `src/app/` (§3.4). **[Diseño UI]**

### 5.3 Estados por vista (resumen)

**V-LOGIN** — nominal / carga (isLoading, sin doble envío) / error token inválido (401, reintentable) / **no autorizado (403 → V-ACCESO-DENEGADO, no reintentable)** / Google caído (502) / edge: ya hay sesión → redirige a `/mapa`. El edge clave: distinguir 401 (reintentable) de 403 (alta manual, no reintentable).

**V-ACCESO-DENEGADO** — pantalla terminal; explica el alta manual; sin carga ni error; maneja la llegada directa sin contexto.

**V-MATRIX** — carga inicial (esqueleto con forma de rejilla) / nominal / vacío sin semanas / vacío en ventana navegada / recarga al cambiar ventana (overlay) / análisis caído (502) / **esquema no coincide (500 `analysis_schema_mismatch`, cara visible de la validación defensiva)** / parcial: celda sin dato / edge: tres estados de celda nominales + "sin dato" como cuarto / edge: ventana muy ancha → navegación, no scroll infinito de 150 columnas. **Nota de riesgo: estos estados se diseñan sobre la forma supuesta del endpoint de matriz (R1, no confirmado); ver §9.** **【REV-CTO: I2】**

**V-COMPANY** — carga / nominal / 404 empresa / 404 semana / parcial: métricas null → "—"/"sin dato", **nunca 0** / parcial: cualitativos vacíos → "sin análisis", resto intacto / edge: bloque cualitativo entero null, la ficha sigue útil. **Nota: el conjunto concreto de campos depende de R2-bis; los estados aquí son estructurales y se mantienen cualquiera que sea el catálogo final.** **【REV-CTO: C1】**

**V-BT-LISTA** — carga / nominal / vacío (CTA "lanzar" solo si analyst) / recarga "cargar más" (añade al final) / error / edge: estados mixtos (cada fila su badge) / edge: filtro por estado sin resultados. **Orden: solo por recencia (cursor); sin orden por columna día uno (I4).**

**V-BT-LANZAR** — nominal (defaults 1/N, USD) / edge sin permiso (RoleGate + 403 de respaldo) / validación 422 invalid_period junto al campo / validación 422 invalid_capital junto al campo / 400 mal formado (global) / envío (isLoading, al 202 navega + Toast "en cola") / edge doble envío bloqueado. Validación cliente posible, pero el 422 del servidor es la autoridad.

**V-BT-RESULTADO** — dos capas superpuestas:
- *Petición (polling):* carga inicial / 404 no existe / error de red en una iteración (no rompe, reintenta el siguiente ciclo; Toast solo si persiste).
- *Dominio:* `pending` (en cola) / `running` (progreso honesto por semanas) / `completed` (resultado completo, para polling) / `failed` (error legible, sin `context`, ofrece relanzar) / `cancelled` (sin resultado).
- *Edge cases del asincronismo:* `/result` con 409 (no error: "aún no"; no se pide hasta ver completed) / cancelar uno ya acabado → 409 (refresca, sin error rojo) / cancelación nominal (ConfirmDialog destructive → 202 → el polling lo verá; Toast "cancelado") / viewer intenta cancelar (RoleGate + 403) / pestaña en background (pausa/reanuda polling) / backtest estancado (visible por progreso honesto, sin timeout artificial) / `/snapshot` con 409 (solo si completed) / recarga (F5) en running (reanuda desde el estado del servidor).

**V-NOT-FOUND y transversales** — ruta interna inexistente → EmptyState; 401 en cualquier petición → redirige a login (transversal); pérdida de conexión global → aviso no intrusivo (Toast), mantiene dato cacheado.

### 5.4 Componentes con estado propio

`DataState<T>` (es el de estados), `BacktestProgress` (pending sin barra / running por semanas / terminal oculto; nunca %), `BacktestStatusBadge` (los cinco valores, incluido `cancelled`), `SelectionMatrix`/`MatrixCell` (cuatro estados de celda), `CursorPager` (hasMore / isLoadingMore / sin más), `Button` (nominal / isLoading→disabled / disabled).

### 5.5 Estado de rol `admin` día uno 【REV-CTO: M2】

`admin` está en el enum (`Role`) como reservado, sin capacidades propias definidas en F2. Decisión de UI día uno: **`admin` ve exactamente lo mismo que `analyst`** (puede consultar y lanzar/cancelar backtests), coherente con F0 ("el administrador puede todo lo que pueden los demás roles"). No se le muestra ninguna pantalla de administración (pospuesta) ni capacidad fantasma. Cuando llegue la UI de administración, `admin` ganará sus capacidades propias; hasta entonces, su experiencia es la de un analyst. Esto evita que un usuario con `admin` vea una UI rota o vacía. **[Diseño UI, deriva de F0 + F2 §5.1]**

### 5.6 Principios transversales del manejo de estados

- **`null` nunca es `0` ni vacío silencioso.** En datos financieros, un cero falso induce decisiones erróneas. Regla, no detalle. **[Heredada de F2 §6.4]**
- **409 del backtest no es error de usuario:** es información de sincronía ("aún no" / "ya cambió"). **[Heredada de F2 §6.6]**
- **El estado de proceso vive en el servidor, no en el cliente:** recargar o volver más tarde reanuda correctamente. **[Heredada de F2]**
- **Carga inicial ≠ recarga:** esqueleto solo cuando no hay nada; overlay sutil cuando ya hay dato. **[Diseño UI]**

---

## 6. Flujo de estado y consumo de la API

### 6.1 Tres clases de estado, dueño único

**Cada dato tiene un único dueño, y el dueño determina dónde vive.**

| Clase | Qué es | Dueño / dónde vive | Quién manda en conflicto |
|---|---|---|---|
| Estado de servidor | Semanas, empresas, backtests, sesión | Capa de datos, en hooks de la vista (estrato 4) | El servidor siempre |
| Compartido de cliente | Sesión/rol resuelta, avisos globales | Contexto único de app | Derivado del servidor; el servidor manda |
| Local de UI | Celda activa, panel abierto, form sin enviar | El componente que lo posee | El cliente; el servidor ni lo conoce |

**Principio rector:** el estado de servidor **no se copia** al de cliente. La UI lee la cache de servidor; copiar crea dos fuentes de verdad. **[Diseño UI]**

La sesión es a la vez de servidor (origen `/auth/me`) y compartida: se lee una vez al arrancar (ver estado de arranque §5.2), se publica en el contexto, y el contexto es **solo lectura** para sus consumidores. **[Diseño UI, deriva de F2 §6.3]**

**Caso especial — la ventana de semanas de la matriz 【REV-CTO: I3】.** La ventana de semanas visible (qué rango `from..to` se muestra) **parametriza la petición** `GET /screening/matrix?from=&to=`. Por tanto **no es estado local del componente `SelectionMatrix`**, sino **estado de la vista `MatrixView`**: la vista la posee, la usa para construir la query, y se la pasa a `SelectionMatrix` por props. `SelectionMatrix` emite `onWindowChange` hacia arriba cuando el usuario navega; no guarda la ventana dentro. Esto es coherente con "controlados, no autónomos" (§4.5) y evita la doble fuente de verdad (componente que cambia la ventana vs vista que dispara la petición) que la v1 dejaba sin resolver. **[Diseño UI]**

### 6.2 Mapa de consumo de la API

| Vista | Operación sobre F2 | Clase de estado |
|---|---|---|
| Arranque | lee `GET /auth/me` | sesión → contexto compartido (§5.2) |
| LoginView | muta `POST /auth/google` | tras éxito, refresca sesión |
| MatrixView | lee `GET /screening/matrix` [R1] + `GET /weeks`; **posee la ventana** | servidor, cache por rango |
| CompanyView | lee `GET /weeks/{s}/companies/{t}` | servidor, cache por (semana,ticker) |
| BacktestListView | lee `GET /backtests` paginado | servidor, cache de lista + cursor |
| BacktestNewView | muta `POST /backtests` → 202 | invalida la lista y navega al `:id` |
| BacktestResultView | poll `GET /backtests/{id}` → lee `/result` | servidor, polling con parada |

**Patrón único:** vista pide a la capa de datos → recibe `{status, data, error}` normalizado → lo pasa a `DataState<T>` → `DataState` decide qué pintar. Ningún componente bajo la vista sabe de dónde vino el dato. **[Diseño UI, cierra la frontera 3↔4]**

### 6.3 Conflictos servidor↔UI y su resolución

| # | Conflicto | Quién gana | Mecanismo |
|---|---|---|---|
| C1 | Backtest nuevo no está aún en la lista | Servidor | Invalidar cache de lista tras 202 (no insertar a mano) |
| C2 | Estado del backtest cambió bajo los pies (cancelar uno que ya acabó) | Servidor | 409 como "vista caduca" → refrescar y mostrar estado real, no error rojo |
| C3 | Optimista vs pesimista | — | **Pesimista día uno en todas las mutaciones**; UI pura es inmediata |
| C4 | Cache obsoleta vs servidor | Servidor | Stale-while-revalidate: muestra lo cacheado y revalida sin parpadeo |
| C5 | Sesión caída a media sesión | Servidor | 401 transversal → login guardando destino; lo local se pierde |
| C6 | Rol en cliente vs autorización real | Backend | Rol cosmético en cliente; 403 manda; nunca hay conflicto de seguridad |
| C7 | Dos pestañas divergentes | Servidor | Convergen por polling; sin sincronización día uno (costura) |
| C8 | Frecuencia de polling | — | Solo si la vista está montada y el estado no es terminal; pausa en background (criterio en §6.5) |

Los centrales: **C2** (el 409 del backtest se trata como vista caduca, no como error) y **C6** (rol cosmético vs autorización en backend, línea roja de F1 §5).

### 6.4 Mapa de invalidación por mutación 【REV-CTO: I6】

"Las mutaciones invalidan, no parchean" (§6.6) necesita un alcance explícito, o cada cambio se decide ad hoc y aparecen los bugs de "no se actualizó" o "recargué media app". Alcance tabulado:

| Mutación | Qué se invalida (se marca obsoleto y se repregunta) | Qué NO se toca |
|---|---|---|
| `POST /backtests` (202) | Lista de backtests (`GET /backtests`) | Screening, sesión |
| `POST /backtests/{id}/cancel` | Ese backtest (`GET /backtests/{id}`) y la lista | Screening, otros backtests |
| `POST /auth/logout` | Todo el estado de servidor (se limpia la cache al cerrar sesión) | — |
| `POST /auth/google` (login) | Se puebla la sesión; no invalida nada previo (no había) | — |

El polling de `BacktestResultView` mantiene fresco el backtest en curso sin necesidad de invalidación manual adicional. El mapa vive en `src/lib/` (§3.4) como punto único de verdad de la política de invalidación. **[Diseño UI]**

### 6.5 Criterio de polling 【REV-CTO: M6】

No se fija un número (es detalle de construcción), pero sí el **criterio**, porque el polling sin guía es justo el bucle que el rate limiting de F2 §6.1 teme:

- **Cuándo:** solo mientras `BacktestResultView` está montada y el estado es `pending`/`running`.
- **Cadencia:** intervalo del orden de pocos segundos (no sub-segundo); suficiente con el progreso honesto por semanas, que no exige refresco agresivo.
- **Backoff:** si una iteración falla (red/5xx), espaciar reintentos en vez de martillear; volver a la cadencia normal al recuperar.
- **Parada:** en cuanto el estado es terminal (`completed`/`failed`/`cancelled`), el polling cesa.
- **Pausa:** si la pestaña pasa a segundo plano, se pausa; se reanuda al volver al foco.
- **Tope:** un límite de duración razonable tras el cual se deja de sondear y se ofrece refresco manual (un backtest que excede el tope es señal de problema, no de paciencia).

**[Diseño UI, deriva de F2 §6.1/§6.5]**

### 6.6 Principios transversales del flujo de estado

- **El servidor es la única fuente de verdad; la UI lo refleja, no lo posee.** Cuando discrepan, el cliente repregunta. No se copia servidor a cliente. **[Diseño UI]**
- **Servidor y UI no se mezclan en el mismo contenedor** (el sort de una tabla y sus filas viven separados aunque se pinten juntos). **[Diseño UI]**
- **Las mutaciones invalidan, no parchean** la cache; el alcance está tabulado en §6.4. **[Diseño UI]**
- **Lo efímero muere sin pena:** el estado local se pierde al recargar o caer la sesión, y está bien. **[Diseño UI]**

---

## 7. Criterios transversales: responsive

**Escritorio-primero con degradación digna**, no móvil-primero. Es una herramienta interna de análisis usada en sesiones de trabajo; F0 no menciona móvil y el perfil de uso (matrices densas, fichas, gráficos comparados) es de pantalla grande. Decisión, no olvido. **[Diseño UI, deriva del perfil de uso de F0]**

| Rango | Nombre | Comportamiento general |
|---|---|---|
| < 640px | Móvil | Soportado, no optimizado; nav colapsa, una columna |
| 640–1024px | Tablet | Una columna ancha; nav lateral colapsable |
| 1024–1440px | Escritorio | Objetivo principal; layout completo |
| > 1440px | Escritorio amplio | Más columnas/semanas visibles |

Piezas no triviales:

- **`SelectionMatrix`** — una rejilla bidimensional no colapsa a una columna sin perder sentido. Columna de empresa **sticky**, eje de semanas con **scroll horizontal** en cualquier tamaño; el nº de semanas visibles por defecto se reduce en pantallas menores (~8 en tablet vs ~26 en escritorio amplio), navegables. En móvil prima legibilidad de celda sobre cantidad de semanas. No se "aplana" la matriz. **[Diseño UI]**
- **`EquityChart` / `DrawdownChart`** — mantienen relación de aspecto y se reescalan al ancho; bajo cierto ancho, la leyenda pasa de lateral a inferior y baja la densidad de etiquetas del eje. Nunca se recortan datos, solo densidad visual. **[Diseño UI]**

Regla transversal: la **navegación persistente colapsa** a un disparador bajo escritorio; el contenido nunca queda detrás de la nav. **[Diseño UI]**

---

## 8. Criterios transversales: accesibilidad

Criterio rector: **WCAG 2.1 nivel AA** como mínimo aplicable a todo el sistema. Mucho viene resuelto por Radix (parte de por qué se eligió esa base), lo que impone una regla: **al envolver un primitivo de Radix no se rompe su accesibilidad** — ni se quitan sus ARIA, ni se intercepta su foco, ni se eliminan sus etiquetas. El estilo se añade; el comportamiento accesible se preserva. **[Diseño UI, deriva de la base elegida]**

Requisitos que **todo componente** cumple:

- **Roles y semántica.** HTML semántico real (un botón es `<button>`); ARIA solo donde lo nativo no basta; landmarks para las regiones principales; los estados se comunican por ARIA, no solo por color (un campo con error lleva `aria-invalid` + `aria-describedby`, no solo borde rojo). **[Diseño UI]**
- **Foco.** Foco visible siempre (nunca `outline:none` sin sustituto); orden de tabulación según orden visual; en diálogos, foco atrapado mientras abren y devuelto al disparador al cerrar (Radix lo da, no romperlo); al navegar entre rutas en la SPA, el foco va al encabezado de la nueva vista para que el lector de pantalla anuncie el cambio. **[Diseño UI]**
- **Navegación por teclado.** Toda acción de ratón alcanzable por teclado. En esta app: las **celdas de la matriz** navegables y activables por teclado (Enter abre ficha); "cargar más" es un botón real enfocable. **[Diseño UI]**
- **Contraste y color.** AA mínimo (4.5:1 texto normal, 3:1 texto grande y elementos de UI). Crítico aquí: los estados de celda de la matriz (no estuvo / universo / seleccionada / sin dato) y los del badge de backtest **no se distinguen solo por color** — llevan también forma, icono o texto. Enlaza con null≠0: "sin dato" se distingue de "no estuvo" por algo más que color. **[Diseño UI, deriva de §5]**
- **Texto y zoom.** Zoom del navegador al 200% sin pérdida de función ni scroll horizontal salvo en la matriz; fuentes en unidades relativas. **[Diseño UI]**
- **Movimiento.** Respetar `prefers-reduced-motion`: las transiciones (overlays de recarga, animación de progreso) se reducen o eliminan a petición del usuario. **[Diseño UI]**

### 8.1 Tema claro/oscuro — aplazado con registro 【REV-CTO: M3】

shadcn + Tailwind soportan tema oscuro a coste bajo, y una herramienta de análisis usada en sesiones largas es candidata natural. **Decisión: se aplaza a una iteración posterior, no día uno.** **[Diseño UI]**

**Porqué aplazarlo:** no es funcionalidad de producto (F0 no lo pide), añade una dimensión de prueba (cada estado de celda y badge debe verificar contraste AA en ambos temas, y el "color no es único canal" se duplica) y el día uno prioriza el visor y el backtest funcionando. **Por qué dejarlo preparado:** definir los colores como **tokens semánticos** desde el principio (no colores literales) hace que añadir el tema oscuro luego sea enchufar un juego de tokens, no repintar componentes. **Costura concreta:** usar variables de tema de Tailwind/shadcn desde día uno; el tema oscuro queda como una iteración barata. **Alternativa descartada:** hacerlo día uno — coste de prueba doble sin demanda de negocio. **[Diseño UI]**

Dos principios que cierran:

- **Accesibilidad heredada que no se rompe** al estilar Radix. **[Diseño UI]**
- **Color nunca es el único canal de información:** estado, error y categoría siempre tienen un segundo canal (texto, icono, forma). **[Diseño UI]**

---

## 9. Registro de realimentaciones a Fase 2 (cerrada — requieren validación)

Esta fase de UI descubrió necesidades que tocan el contrato de F2. **No se aplican aquí; se registran para validación de quien posee F2.**

- **R1 — Falta un endpoint para el mapa histórico (matriz).** La pieza central del visor (V-MATRIX) es una vista transpuesta y multi-semana (rango de semanas → unión de empresas → estado por celda) que los endpoints actuales (`GET /weeks`, `GET /weeks/{week_date}/companies`) no sirven directamente. Componer en cliente colocaría en el front la lógica de "unión de empresas" y "qué cuenta como seleccionada", que pertenece al dominio (`WeekResolver`). Propuesta a especificar: `GET /screening/matrix?from=&to=` que devuelva ejes resueltos y celdas dispersas. Magnitud confirmada (decenas de empresas × 26–150 semanas): barato en servidor, sin virtualización agresiva en cliente día uno.
  **Nota de riesgo de planificación 【REV-CTO: I2】:** sobre este endpoint **no confirmado** ya se ha invertido diseño de UI aguas abajo — el catálogo de estados de celda (§5.3), el comportamiento responsive (§7) y los requisitos de teclado (§8) de `SelectionMatrix`. Si el contrato real de la matriz difiere de la forma supuesta (celdas dispersas con ejes resueltos), parte de ese diseño se rehace. Es una decisión consciente de no bloquear; el riesgo queda visible aquí en vez de oculto. **[Realimentación F2]**
- **R2 — Filtros y `sort` del screening "a concretar" (F2 §6.4).** El contrato deja sin definir los filtros por métrica y el orden de `GET /weeks/{week_date}/companies`. Condiciona la interacción de filtrado/orden del visor. Se concretará realimentando el contrato. **[Realimentación F2]**
- **R2-bis — Catálogo de campos de la ficha de empresa 【REV-CTO: C1】.** Distinto de R2 (que es filtros/sort de la *lista*): aquí se trata de **qué subconjunto de las 128 columnas de `processed_stocks` y qué estructura de cualitativos LLM** expone `GET /weeks/{week_date}/companies/{ticker}` para la *ficha*. Sin ese catálogo, los componentes `CompanyMetrics`/`CompanyQualitative` tienen su contrato de props pendiente (§4.3). La estructura y los estados de V-COMPANY se diseñan sin él (son estables); los campos concretos, no. **[Realimentación F2]**
- **R3 — Nomenclatura de roles divergente.** F0 usa Administrador / Consulta+Backtest / Solo consulta; F2 usa admin / analyst / viewer. Mismo mapa, etiquetas distintas. La UI necesita fijar qué etiquetas (en español) ve el usuario. Detalle menor, a cerrar en el detalle visual. **[Diseño UI / Realimentación F2]**

---

## 10. Registro de decisiones de diseño UI (con alternativas descartadas)

| Decisión | Porqué | Alternativa descartada |
|---|---|---|
| Reparto autenticado/no-autenticado vía guardián de rutas, no público/privado | SPA tras login sin SEO; todo `noindex` | Estrategias de renderizado distintas por página (no aplica en SPA pura) |
| Entrada por defecto a `/mapa` | El visor es el corazón; lo ven los tres roles | Dashboard de entrada (el panel está pospuesto en F0) |
| Ficha de empresa como ruta anidada direccionable | Enlace directo y back del navegador en una herramienta de análisis | Panel efímero no direccionable |
| Lanzar backtest como ruta propia | El formulario tiene entidad y conviene enlazable | Modal |
| Una sola ruta `/backtests/:id` para los tres estados | El estado lo resuelve el polling, no la URL | Rutas distintas por estado |
| Ruta `/backtests/comparar` prevista + charts con N series **【C2】** | Comparar enchufable (F1 §9.7) sin rediseño | Dejar comparar como "costura" sin verificar (lo hacía v1) |
| shadcn/Radix + Tailwind como base | Accesibilidad difícil resuelta + control de diseño + peso/mantenimiento para una persona | Sistema propio (desproporcionado); MUI (estética impuesta, peso, no resuelve piezas difíciles) |
| recharts como librería de charts **【M5】** | Declarativa, nativa de React, aridad-N, peso razonable | visx (demasiado bajo nivel); nivo (pesado/opinado); Chart.js (imperativo, encaja peor) |
| Cuatro estratos; solo las vistas tocan la API | Componentes testeables y reutilizables; sin contaminación de dominio | Dominio con sus propios hooks de datos (mezclaría responsabilidades) |
| `SelectionMatrix` componente propio, no `DataTable` | No es una tabla: rejilla transpuesta, dos ejes, celdas dispersas | Variante de DataTable (forzaría el patrón equivocado) |
| `DataState<T>` único y genérico | Concentra la robustez ante datos ausentes/erróneos una vez | Manejo de estados caso por caso (se olvidan los no-felices) |
| Componentes base controlados, no autónomos | Una sola fuente de verdad, en la vista | Estado interno en cada componente (divergencia) |
| Ventana de semanas en la vista, no en el componente **【I3】** | Parametriza la petición; debe vivir donde se dispara | Estado local del componente (doble fuente de verdad) |
| Lista de backtests sin orden por columna día uno **【I4】** | El contrato solo da orden por recencia (cursor) | Prometer orden por columna que el backend no da |
| `CursorPager` "cargar más", sin ver el cursor | Coherente con cursor opaco de F2 | Numeración de páginas (offset; saltos/duplicados) |
| Charts y MetricsPanel con contrato cerrado ya **【I1】** | Su forma de dato está definida (F2 §5.2); no depende de R2 | Aplazarlos con el resto del estrato 3 (lo hacía v1, sin justificar) |
| Estado de arranque "resolviendo sesión" **【I5】** | Evita el flash de login / pantalla en blanco | No definirlo (la construcción improvisa) |
| Mapa de invalidación tabulado **【I6】** | Cero decisiones ad hoc en mantenimiento | Principio "invalida, no parchea" sin alcance (lo hacía v1) |
| Frontera guardián (rutas) vs RoleGate (elementos) **【M1】** | Evita doble lógica de autorización cosmética | Dejar el solape sin aclarar |
| `admin` ve lo mismo que `analyst` día uno **【M2】** | F0: admin puede todo lo de los demás; evita UI rota | Dejar sin definir qué ve admin |
| `Toast` asignado a confirmaciones/errores transitorios **【M4】** | Da uso al primitivo; encaja con mutaciones | Tenerlo en el inventario sin uso |
| 409 del backtest como estado de flujo, no error | Es sincronía ("aún no"/"ya cambió"), no fallo del usuario | Pintar 409 como error rojo (confundiría) |
| `null` ≠ `0` como regla dura en todo el visor | Un cero falso induce error de inversión | Tratar null como detalle de cada componente |
| Carga inicial ≠ recarga | Evita el parpadeo en uso intensivo | Esqueleto en toda recarga |
| Pesimismo en todas las mutaciones día uno | El estado del backtest puede cambiar; coste de error alto | Optimismo (costura futura si algo se siente lento) |
| Sin sincronización entre pestañas día uno | Convergen por polling; complejidad sin necesidad a esta escala | Sync entre pestañas (costura) |
| Criterio de polling registrado, sin número **【M6】** | Guía sin atarse a un valor; evita el bucle que teme F2 §6.1 | Delegar el polling sin criterio a construcción |
| Escritorio-primero con degradación digna | Herramienta interna de análisis en sesiones de trabajo | Móvil-primero (no encaja con el perfil) |
| WCAG 2.1 AA como listón | Ni negligente (sub-AA) ni desproporcionado (AAA) para herramienta interna | AAA (excesivo); por debajo de AA (negligente) |
| Tema oscuro aplazado, tokens semánticos día uno **【M3】** | Sin demanda de negocio; coste de prueba doble; queda barato de añadir luego | Hacerlo día uno (coste sin demanda) |

---

## 11. Resumen ejecutivo

- **Arquitectura de UI:** SPA, todo en cliente; frontera real autenticado/no-autenticado resuelta por un guardián de rutas; cuatro vistas-día-uno de visor+acceso y tres de backtesting; entrada por defecto a `/mapa`; ficha de empresa anidada y direccionable; una sola ruta por backtest para sus tres estados; ruta de comparar prevista con costura verificada.
- **Base de componentes:** shadcn/Radix + Tailwind; recharts para los charts (decisión registrada). Las dos piezas difíciles (matriz y charts) se construyen/integran aparte en cualquier escenario.
- **Jerarquía:** cuatro estratos separados por cuánto saben de dominio/servidor; la frontera dura es que solo las vistas tocan la API; importación dirigida en un solo sentido.
- **Contratos base:** diez componentes de estrato 2 con props tipadas, eventos `on*`, variantes cerradas; `DataState<T>` como columna vertebral; además se cierran ya los contratos de los charts (N series) y `MetricsPanel` (N columnas), que no dependían de R2.
- **Estados:** catálogo exhaustivo por vista y componente, más el estado global de arranque; `V-BT-RESULTADO` con dos capas y ~8 edge cases del contrato asíncrono; principios null≠0, 409≠error, estado en servidor, carga≠recarga.
- **Flujo de estado:** tres clases con dueño único, sin copiar servidor a cliente; la ventana de la matriz reubicada en la vista; mapa de consumo por vista; ocho conflictos servidor↔UI resueltos; mapa de invalidación tabulado; criterio de polling registrado; pesimista día uno.
- **Transversales:** escritorio-primero con degradación digna y cuatro breakpoints; WCAG 2.1 AA, accesibilidad de Radix preservada, color nunca como único canal; tema oscuro aplazado con tokens semánticos preparados.
- **Realimentaciones a F2:** R1 (endpoint de matriz, con nota de riesgo), R2 (filtros/sort de la lista), R2-bis (catálogo de campos de la ficha), R3 (nomenclatura de roles).

La fase de diseño de UI, revisada tras la auditoría del CTO, queda consolidada. El siguiente paso del proceso es la **construcción** del frontend sobre el repositorio real, dentro de este marco, primero el andamiaje y los componentes base, después las vistas, con el catálogo de estados y los conflictos de §6 como guía de los caminos no-felices. Antes de construir el visor conviene cerrar R1 y R2-bis contra F2.

---

## 12. Cambios incorporados tras la auditoría de diseño (CTO)

Resumen de qué resolvió la auditoría, para trazabilidad. Cada hallazgo, su severidad y dónde se resolvió:

| Hallazgo | Severidad | Qué era | Dónde se resolvió |
|---|---|---|---|
| **C1** | Crítico | La ficha se diseñaba sobre campos no definidos por el contrato; hueco no registrado | R2-bis (§9); nota en V-COMPANY (§1.3, §5.3); contrato pendiente en §3.3/§4.3 |
| **C2** | Crítico | "Comparar" declarado costura sin verificar que la arquitectura no lo cierra (F1 §9.7) | Verificación de costura §1.5; ruta prevista §1.4; charts N-series §4.3 |
| **I1** | Importante | Charts sin contrato de props, aplazados sin que su dependencia lo justificara | Contratos cerrados en §4.3 (EquityChart, DrawdownChart, MetricsPanel) |
| **I2** | Importante | Inversión de diseño aguas abajo de un endpoint (R1) no confirmado | Nota de riesgo de planificación en R1 (§9); nota en V-MATRIX (§5.3) |
| **I3** | Importante | Ventana de semanas como estado local, pero parametriza la petición | Reubicada en `MatrixView` (§6.1, §3.2, §6.2) |
| **I4** | Importante | `DataTable` ofrece orden por columna que `GET /backtests` no soporta | Lista sin orden por columna día uno (§4.2, §5.3) |
| **I5** | Importante | Sin estado para el arranque (resolución de sesión); flash de login | Estado de arranque §5.2; carpeta `src/app/` §3.4 |
| **I6** | Importante | Invalidación de cache sin alcance definido | Mapa de invalidación tabulado §6.4 |
| **M1** | Menor | Solape guardián / RoleGate sin aclarar | Frontera aclarada §1.4 |
| **M2** | Menor | Sin estado de UI para `admin` reservado | `admin` = `analyst` día uno (§5.5) |
| **M3** | Menor | Tema claro/oscuro ni decidido ni descartado | Aplazado con tokens semánticos preparados (§8.1) |
| **M4** | Menor | `Toast` en el inventario sin uso | Uso asignado (§3.3) |
| **M5** | Menor | Librería de charts mencionada sin decidir/registrar | Decisión registrada con alternativas (§2.1) |
| **M6** | Menor | Polling delegado a construcción sin criterio | Criterio registrado (§6.5) |

**Observación de la auditoría, registrada:** la mitad de los hallazgos serios (C1, C2, I1, I2, I4) tenían una raíz común — el documento diseñó sobre contratos de F2 abiertos (matriz, catálogo de campos, sort) o aplazó contratos de UI que sí podía cerrar (charts). La corrección cierra lo cerrable (charts, §4.3) y hace visibles y acotadas las dependencias abiertas (R1 con nota de riesgo, R2-bis nuevo, I4 resuelto contra el contrato real). C2 e I1 se resolvieron como una sola decisión: la aridad-N de los charts.
