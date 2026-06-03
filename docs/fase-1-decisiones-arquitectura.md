# Documento de Decisiones de Arquitectura

**Producto:** Webapp de soporte a un screening de empresas de bolsa (USA / NASDAQ)
**Fase:** 1 — Arquitectura y stack
**Estado:** Cerrado tras corrección. Auditoría de diseño pasada en dos vueltas sin defectos críticos; correcciones de integridad documental aplicadas. Listo como entregable de la Fase 1.
**Entrada heredada:** Documento de Definición de Funcionalidades (Fase 0) y esqueleto de aplicación ya iniciado.

---

## Cómo leer este documento

Cada decisión se registra con su porqué y, donde aplica, las alternativas descartadas. Para mantener la disciplina de la fase, cada elemento se etiqueta como una de tres cosas:

- **[Heredada F0]** — decisión de negocio o de producto que viene de la Fase 0 y que esta fase respeta sin redecidir.
- **[Diseño nuevo]** — preferencia o decisión de arquitectura tomada en esta fase.
- **[Acción F2+]** — trabajo de ejecución que esta fase no toca, solo deja registrado para fases posteriores (diseño de servidor/datos, construcción).

La Fase 1 decide arquitectura y stack. **No escribe código, no diseña esquemas ni contratos.** Todo lo marcado como acción pertenece a la Fase 2 o posteriores.

---

## 1. Resolución del gate de entrada

Antes de decidir nada se cerraron las ambigüedades de la Fase 0 que bloqueaban razonar la arquitectura con criterio. Resoluciones aportadas por negocio:

1. **Esquema de la base de datos de análisis: estable.** Se trata como contrato fijo de lectura. **[Heredada F0]**
2. **Precios de mercado: vía yfinance / Yahoo Finance "por ahora".** La app los obtiene; no vienen pre-guardados por el proceso externo. **[Heredada F0]**
3. **Conversión de divisa: tipo de cambio del día de cotización**, para tickers que cotizan fuera de USD. **[Heredada F0]**
4. **Tipos de cambio (FX): misma fuente que los precios (yfinance).** Simplifica a una sola fuente de datos de mercado. **[Heredada F0]**
5. **Backtests: se persisten** desde el día uno, aunque la pantalla de comparación llegue después. **[Heredada F0]**
6. **Pendientes de Fase 0 (plazos, presupuesto, equipo): retirados** por negocio; no condicionan esta fase. **[Heredada F0]**

Con estas respuestas, el documento de Fase 0 se consideró suficiente para decidir stack y arquitectura. No fue necesario devolver preguntas a negocio.

---

## 2. Mapa de implicaciones de los atributos transversales de Fase 0

Traducción de cada atributo de negocio a su implicación técnica, como base de las decisiones posteriores.

| Atributo de Fase 0 | Implicación técnica | Etiqueta |
|---|---|---|
| Todo tras login, sin SEO ni parte pública | Sin presión de renderizado en servidor; la latencia que importa es la de la API y las transiciones internas, no el primer pintado para buscadores. Abre la puerta a una SPA. | [Heredada F0] |
| Multiusuario con tres roles | Autenticación y autorización pasan a ser capa de primera clase. La autorización gira casi entera en torno a una capacidad: *lanzar backtests*. | [Heredada F0] |
| Una sola organización, espacio compartido | No hay multitenancy que resolver. El problema real es *deshacer* la multi-workspace que trae el esqueleto. | [Heredada F0] |
| Procesos pesados (precios, backtests) | Asincronía estructural, justificada por la *naturaleza* del trabajo, no por la escala. No caben en el ciclo petición-respuesta. | [Heredada F0] |
| Integraciones con terceros | Encapsular cada tercero tras una frontera propia y mockeable. yfinance es declaradamente sustituible. | [Heredada F0] |
| Escala pequeña y conocida | Libera de las decisiones de alta escala; sesgo hacia lo simple y barato de operar. No elimina la asincronía. | [Heredada F0] |

> **Nota sobre la columna Etiqueta:** lo heredado de Fase 0 es el *atributo* (columna izquierda). La *implicación técnica* (columna central) es análisis de esta fase que alimenta el diseño; la etiqueta [Heredada F0] se refiere al atributo de origen, no al razonamiento, que es propio.

**Punto clave registrado:** la asincronía se justifica por la naturaleza del trabajo (yfinance es lento, el backtest es cálculo), no por el volumen. Aunque hubiera un solo usuario, un backtest seguiría sin caber en una petición HTTP.

---

## 3. Estrategia de renderizado

**Decisión: aplicación de página única (SPA) servida tras autenticación. [Diseño nuevo, confirmando el esqueleto]**

**Porqué:** todo va tras login, sin SEO ni páginas públicas, lo que retira la única familia de razones que justificaría renderizado en servidor. El perfil de uso —usuario autenticado navegando entre mapa, ficha y backtests— encaja con una SPA con estado en cliente y transiciones sin recarga.

**Decisión estructural derivada:** frontend y backend son dos piezas separadas que se comunican por una API HTTP. El backend **no renderiza HTML, sirve datos (JSON)**; toda la presentación vive en el frontend. Esta frontera condiciona la elección de backend (sección 4).

**Alternativa descartada:** renderizado en servidor / framework tipo Next.js. Sin SEO ni primer pintado público que optimizar, no aporta nada y añade complejidad.

**Trade-off asumido:** una SPA tiene un arranque inicial algo más pesado (descarga del JS antes del primer pintado). Para una herramienta de sesiones de trabajo tras login, es irrelevante.

---

## 4. Stack

Stack por defecto del proyecto: React + Python (FastAPI o Django) + PostgreSQL + GitHub con ramas development/test/production. **No hay desvío del stack por defecto en ningún punto.**

### 4.1 Frontend — React (SPA)

**Decisión: React como SPA. [Heredada F0 (esqueleto) + Diseño nuevo (confirmación)]**

**Porqué:** es el stack por defecto, el esqueleto ya lo trae montado así, y encaja con la frontera SPA↔API. Confirmarlo respeta el trabajo heredado y es la opción correcta para el perfil de uso.

### 4.2 Backend — FastAPI

**Decisión: FastAPI. [Diseño nuevo]** Es la única elección del stack con dos caminos legítimos; se razona en detalle.

**Porqué FastAPI y no Django:**

- El grueso de la app **no es CRUD**: es lectura (la app consume una BBDD que puebla un proceso externo) y cálculo asíncrono (backtests). El único CRUD real es la gestión de invitados/roles, que negocio aplazó.
- La mayor baza de Django —su panel de administración automático— **administra modelos de la propia base de datos**, y aquí la base de análisis la posee y puebla un proceso externo. El admin encaja mal con una BBDD de la que somos consumidores.
- La naturaleza de la app es **API + lógica a medida + trabajo asíncrono**, no vistas servidas. FastAPI está construido para exactamente eso, con validación de E/S de primera clase y modelo asíncrono nativo.

**Alternativa descartada — Django:** su admin para CRUD es la baza que lo justificaría, pero es marginal aquí (única pieza CRUD, aplazada) y choca con que la BBDD no es nuestra.

**Trade-off asumido:** se renuncia al admin automático y a las "baterías incluidas". La gestión de invitados/roles, cuando llegue su pantalla, se construye a mano (pieza pequeña). A cambio: menos framework sin usar, herramienta ajustada a lo que la app necesita.

**Nota de fondo registrada:** la decisión real es *un backend orientado a API, no a vistas*, coherente con el frontend SPA.

### 4.3 Base de datos — PostgreSQL (dos instancias)

**Decisión: PostgreSQL en ambos casos — una preexistente (análisis) y una nueva (app), como bases separadas. [Heredada F0 + Diseño nuevo]**

- **BBDD de análisis** (existente en Railway): la puebla el proceso externo, esquema estable, la app tiene **solo lectura**. No se añade nada nuestro. **[Heredada F0]**
- **BBDD propia de la app** (nueva): lectura-escritura. Contiene el estado propio: usuarios/invitados y roles, backtests persistidos (snapshot completo, ver sección 7.1) y caché de precios/FX. **[Diseño nuevo]**

**Porqué dos y no una:** negocio confirmó que la base de análisis es de su propiedad y no debemos escribir en ella. Dos bases dan **aislamiento estructural**: la app se conecta a la de análisis con credenciales de solo lectura, y es físicamente incapaz de escribir donde no debe.

**Trade-off asumido:** las operaciones que cruzan los dos mundos (el backtest lee selecciones de análisis y escribe resultados en la propia) ya no son una consulta simple; las orquesta la aplicación. Encaja de forma natural dentro de la lógica de backtest, que de todos modos es trabajo asíncrono a medida.

**Alternativa descartada — una sola instancia con dos esquemas:** se descartó porque negocio indicó que la base de análisis es ajena y no se le añade nada.

### 4.4 Repositorio — GitHub

**Decisión: GitHub con ramas development / test / production. [Heredada F0 (stack por defecto)]** El flujo entre ramas y los gates es proceso, no se redecide aquí.

---

## 5. Capas transversales — reparto día uno / costura preparada

"Costura preparada" es una decisión activa: diseñar de forma que añadir esa capa más tarde sea enchufarla en un punto previsto, no operar a corazón abierto.

| Capa | Clasificación | Núcleo del enfoque | Etiqueta |
|---|---|---|---|
| Autenticación | Día uno | Identidad delegada en Google; no se gestionan contraseñas. | [Heredada F0] |
| Autorización (mecanismo) | Día uno | Roles simples comprobados **en el backend**; giran en torno a "¿puede lanzar backtest?". | [Heredada F0 + Diseño nuevo] |
| Autorización (UI de admin) | Costura preparada | Alta manual el día uno, escribiendo en las mismas tablas que luego usará la pantalla. | [Heredada F0] |
| Asíncrono — cola + worker | Día uno | Estructural por naturaleza del trabajo. Encolar, devolver acuse inmediato, ejecutar en worker, guardar resultado. | [Heredada F0 + Diseño nuevo] |
| Asíncrono — scheduler | Costura preparada | La misma infraestructura de jobs debe admitir tareas programadas después (refresco de precios). | [Diseño nuevo] |
| Integraciones externas | Día uno (la frontera) | Encapsular Google y yfinance tras fronteras mockeables. Barato ahora, carísimo de retrofitear. | [Heredada F0 + Diseño nuevo] |
| Logging | Día uno | Estructurado y correlacionado (id de backtest en todos sus logs), concentrado en asíncrono e integraciones. | [Diseño nuevo] |
| Métricas | Costura preparada | Derivables del logging estructurado sin reinstrumentar. | [Diseño nuevo] |
| Trazado distribuido | No aplica | No hay malla de microservicios que trazar; lo cubre el logging correlacionado. | [Diseño nuevo] |
| Configuración y secretos | Día uno | Credenciales fuera del código desde el principio (Google, dos juegos de BBDD, yfinance). | [Diseño nuevo] |
| i18n / pagos / notificaciones | No aplican | Herramienta interna cerrada, un idioma, sin cobros. | [Diseño nuevo] |

**Principio registrado (autorización):** se hace cumplir en el backend, en la API, nunca solo escondiendo un botón en el frontend. El frontend oculta por comodidad; el backend impide por seguridad.

**Distinción registrada (asíncrono):** cola+worker es día uno; el scheduler es costura sobre la misma infraestructura. La costura solo queda "gratis" si la herramienta de jobs elegida en Fase 2 admite scheduling nativo — criterio de elección a trasladar a Fase 2.

---

## 6. Tratamiento del esqueleto heredado

| Pieza del esqueleto | Decisión | Porqué | Etiqueta |
|---|---|---|---|
| React SPA | Respetar | Es el stack confirmado. | [Heredada F0] |
| FastAPI | Respetar | Es el stack confirmado. | [Heredada F0] |
| Login Google | Respetar | Es la autenticación de día uno; ya está hecha. | [Heredada F0] |
| yfinance como fuente | Respetar (la fuente) | Fuente "por ahora" de precios y FX. Su *encapsulación* es trabajo a hacer. | [Heredada F0] |
| Moneda EUR → USD | Ajustar | Negocio reporta en USD; conversión por FX del día. Alcance incierto hasta ver el código. | [Heredada F0] → [Acción F2+] |
| Una BBDD → dos | Ajustar | Se decidió dos PostgreSQL; extender la configuración de conexión, no rehacer. | [Diseño nuevo] → [Acción F2+] |
| Encapsulación de yfinance | Ajustar | Las capas piden una frontera mockeable; si el esqueleto la llama directa, se introduce la pared. | [Diseño nuevo] → [Acción F2+] |
| Multi-workspace | **Eliminar** | Negocio quiere un único espacio compartido. El concepto sobra y sería deuda conceptual a 5 años. | [Heredada F0] → [Acción F2+] |

**Sobre eliminar multi-workspace:** decisión firme, no condicional. El esqueleto crea un workspace al registrar usuario; al eliminar el concepto, ese comportamiento de registro también cambia (registrarse da de alta a un usuario en el único espacio por defecto, no crea espacio). **Eliminar el workspace y ajustar el alta de usuario son el mismo trabajo**, a tratar conjuntamente en Fase 2. Se asume que eliminar es más refactorización que simplificar a un workspace latente; se acepta ese coste a cambio de no arrastrar un concepto muerto durante años. El alcance exacto se conocerá al abrir el repositorio.

---

## 7. Decisiones derivadas de la auditoría de diseño

La auditoría no encontró defectos críticos de diseño. Resolvió tres puntos:

### 7.1 Persistencia del backtest — snapshot completo

**Decisión: cada backtest guarda una copia autocontenida (snapshot) de todo lo que usó** — selecciones, empresas, precios y FX. **[Diseño nuevo]**

**Porqué:** un backtest no tiene integridad referencial con la base de análisis (son dos bases distintas) y el proceso externo podría reescribir una selección pasada. Un snapshot hace el backtest **reproducible y auditable**, independiente de cambios externos. A la escala del proyecto, la duplicación de datos es trivial; el beneficio es el núcleo del producto (validar decisiones de inversión exige resultados defendibles).

**Alternativas descartadas:**
- *Referencia pura* — no reproducible: si el proceso externo reescribe una selección, el backtest guardado "miente". Descartada.
- *Híbrido (referencia a selecciones + copia de precios)* — reabre el agujero de "selección reescrita" a cambio de un ahorro de espacio innecesario a esta escala. Descartada frente al snapshot completo.

**Coherencia registrada:** la caché de precios/FX (7.2) y el snapshot son la misma pieza vista dos veces. Si el backtest, al ejecutarse, copia las selecciones leídas y los precios usados (ya en caché), la reproducibilidad sale casi sin trabajo extra.

### 7.2 Caché de precios/FX — día uno

**Decisión: caché de precios y FX en la BBDD propia, día uno, en forma mínima** (guardar lo descargado de yfinance por ticker y fecha, y reutilizarlo). **[Diseño nuevo]**

**Porqué:** materializa la tolerancia a fallo declarada prioritaria al concentrar todo en una única fuente frágil, y hace los backtests reproducibles. "Forma mínima" = guardar y reutilizar, sin política sofisticada de expiración (eso, si hace falta, es el scheduler en costura).

### 7.3 Estabilidad del esquema de análisis — riesgo aceptado

**Decisión: se acepta como riesgo conocido, cubierto con validación defensiva. [Diseño nuevo]** No se traslada pregunta a negocio.

**Porqué:** toda la lectura depende de un esquema externo que no controlamos. En lugar de confiar ciegamente, **la app valida lo que lee y falla de forma clara y diagnosticable** si el esquema no coincide, en vez de producir resultados silenciosamente incorrectos. El riesgo no desaparece (depender de un sistema externo es intrínseco), pero deja de ser ciego.

---

## 8. Riesgos asumidos conscientemente

1. **Fuente de datos de mercado única y frágil (yfinance).** Precios y FX dependen del mismo proveedor no oficial; si cae, caen ambos. Se acepta por simplicidad sostenible (menos piezas a 5 años pesa más que la redundancia). Mitigación: caché día uno, encapsulación, tolerancia a fallo.
2. **Esquema de análisis externo sin contrato verificable.** Aceptado, cubierto con validación defensiva (7.3).
3. **Sin datos de equipo/presupuesto.** A falta de dato, las decisiones favorecen por defecto lo operativamente barato y mantenible por una sola persona.
4. **Coste de refactorización del workspace.** Eliminar es más trabajo que simplificar; se asume a cambio de no heredar deuda conceptual.

---

## 9. Cuestiones a resolver en Fase 2 (diseño de servidor y datos)

No son defectos abiertos; son trabajo de diseño que la Fase 1 deja explícitamente planteado:

1. **Estructura del snapshot del backtest** en tablas de la BBDD propia (concreción de 7.1).
2. **Alcance real del cambio EUR → USD** en el código del esqueleto (centralizado o disperso).
3. **Cómo está enchufado el concepto workspace** en el esqueleto, para dimensionar su eliminación.
4. **Punto e implementación de la frontera mockeable** de yfinance y de Google.
5. **Elección de herramienta de jobs** que admita scheduling nativo (para que la costura del scheduler quede preparada).
6. **Punto y forma de la validación defensiva** al leer la base de análisis.
7. **Verificar que la persistencia de backtests guarda lo necesario para "comparar"** (parámetros de cada backtest, no solo su resultado), aunque la pantalla de comparación llegue después.
8. **Identificador de correlación de logs** ligado al id de job/backtest (resolver junto con el modelo de jobs).

---

## 10. Resumen ejecutivo

- **Renderizado:** SPA tras login. Frontera limpia SPA↔API.
- **Stack:** React (SPA) + FastAPI (orientado a API) + dos PostgreSQL (análisis solo-lectura / app lectura-escritura) + GitHub con ramas development/test/production. Sin desvío del stack por defecto.
- **Capas día uno:** autenticación, mecanismo de autorización, cola+worker asíncrono, frontera de integraciones, logging estructurado, configuración/secretos, caché de precios/FX.
- **Capas en costura:** UI de administración, scheduler, métricas.
- **No aplican:** trazado distribuido, i18n, pagos, notificaciones.
- **Esqueleto:** se respeta React/FastAPI/Google/yfinance; se ajusta EUR→USD, una→dos BBDD y la encapsulación de yfinance; se elimina la multi-workspace.
- **Auditoría:** sin defectos críticos; backtests con snapshot completo, caché día uno, esquema externo como riesgo aceptado con validación defensiva.

La Fase 1 queda cerrada. El siguiente paso del proceso es la **Fase 2 — Servidor y datos**: diseño detallado del esqueleto de backend, modelo de datos, contratos de API y estrategia de testing, sin construir todavía.
