# Documento de Definición de Funcionalidades

**Producto:** Webapp de soporte a un screening de empresas de bolsa (USA / NASDAQ)
**Fase:** 0 — Definición de funcionalidades (visión de producto)
**Estado:** Revisado. Cerrado salvo datos de plazo / presupuesto / equipo (no bloquean Fase 1).

---

## Contexto y objetivo

La app da soporte a un proceso de screening de empresas USA / NASDAQ cuyo análisis se realiza **fuera de la app**. La selección semanal de empresas, su análisis y sus justificaciones ya residen en una base de datos poblada por un proceso externo. La app **no genera el análisis ni lo ingiere mediante carga de ficheros**: lo **lee directamente de la base de datos** y lo presenta.

Sobre esa selección histórica, la app permite además **backtestear** las decisiones tomadas (simular qué habría pasado invirtiendo cada semana en las empresas seleccionadas) y contrastarlas contra benchmarks.

El día uno cubre dos bloques: **visor de resultados** (consultar el análisis) y **backtesting** (validar las decisiones). La parte de valoración y análisis ampliado queda explícitamente aplazada a iteraciones posteriores.

Existe un **esqueleto de aplicación ya iniciado** (backend en Python/FastAPI, base de datos PostgreSQL, frontend React, obtención de precios vía yfinance, login con Google) que servirá de base a la Fase 1. La base de datos PostgreSQL está alojada en **Railway**.

### Actores (roles)

Se definen tres roles, usados de forma consistente en todo el documento:

- **Administrador:** administra el espacio y da acceso a los invitados. Puede todo lo que pueden los demás roles.
- **Consulta+Backtest:** puede consultar el visor y **lanzar** backtests.
- **Solo consulta:** puede consultar el visor y ver resultados de backtests, pero **no lanzarlos**.

Cuando una funcionalidad indica "Todos", se refiere a los tres roles.

---

## Parte 1 — Lista de funcionalidades a alto nivel

### Acceso a los datos (base)

| Funcionalidad | Qué hace | Quién la usa |
|---|---|---|
| Lectura de la selección semanal | La app lee de la base de datos la selección semanal, el universo analizado, las métricas y las justificaciones que el proceso externo ha guardado | Automático (base de todo el visor) |

### Visor de resultados (consultar el análisis)

| Funcionalidad | Qué hace | Quién la usa |
|---|---|---|
| Panel de situación | Vista de entrada con el resumen: semanas disponibles, última semana, nº de empresas | Todos |
| Mapa histórico de selección | Cuadrícula empresa × semana que muestra qué estuvo en el universo y qué se seleccionó cada semana | Todos |
| Ficha de empresa por semana | Detalle de una empresa en una semana concreta: su análisis, métricas y la justificación de por qué se seleccionó (o no) | Todos |
| Resumen de la selección semanal | El relato de la semana: resumen ejecutivo, alertas, diversificación, consideraciones | Todos |

### Backtesting (validar las decisiones)

| Funcionalidad | Qué hace | Quién la usa |
|---|---|---|
| Lanzar un backtest | Definir periodo y parámetros (capital, costes, benchmarks) y ejecutar la simulación sobre las selecciones históricas | Administrador y Consulta+Backtest |
| Resultados de un backtest | Ver métricas de rendimiento y riesgo, la curva de capital y los drawdowns. El contraste contra benchmarks (ver abajo) es una lectura dentro de esta misma pantalla | Todos |
| Contraste contra benchmarks | Dentro de los resultados, comparar el rendimiento frente a alternativas (universo equiponderado, carteras aleatorias, índice externo) | Todos |
| Comparar backtests | Poner varias simulaciones lado a lado para contrastar configuraciones | Todos |

### Acceso y organización

| Funcionalidad | Qué hace | Quién la usa |
|---|---|---|
| Acceso con cuenta Google | Entrar de forma segura sin gestionar contraseñas | Todos |
| Mecanismo de acceso de invitados | Dar de alta a un tercero para que pueda entrar al espacio compartido | Administrador |
| Gestión de invitados y permisos (UI) | Pantalla para invitar, ver y cambiar el rol de los miembros | Administrador |

---

## Parte 2 — Priorización

### Imprescindible (día uno)

| Funcionalidad | Por qué |
|---|---|
| Acceso con cuenta Google | Si lo ven terceros, no hay producto sin puerta de entrada. Condición previa a todo lo demás |
| Mecanismo de acceso de invitados | Para que un tercero entre, alguien tiene que poder darle de alta. El día uno puede hacerse de forma manual (sin pantalla pulida), pero el mecanismo debe existir — es una decisión consciente, no un olvido |
| Lectura de la selección semanal | Sin leer los datos de la BBDD no hay nada que mostrar. Base de todo el visor |
| Mapa histórico de selección | Es el corazón del visor: de un vistazo se ve qué se ha seleccionado semana a semana |
| Ficha de empresa por semana | Sin abrir una empresa y leer su análisis, el mapa son solo colores. Mapa + ficha son el visor mínimo usable |
| Lanzar un backtest + Resultados | Una sola pieza funcional: lanzar sin ver resultado no sirve, ver sin poder lanzar no existe. Es la mitad "backtesting" pedida explícitamente |
| Contraste contra benchmarks | Un backtest sin nada contra qué compararse no permite juzgar la calidad de las decisiones. El motor ya lo trae |

### Puede esperar

| Funcionalidad | Por qué |
|---|---|
| Panel de situación | Resume cosas que ya se ven en el visor. Agradable, no esencial para validar el producto |
| Resumen de la selección semanal | Aporta contexto cualitativo valioso, pero se puede vivir sin él en la v1 si mapa y ficha ya están |
| Comparar backtests | Tiene sentido cuando ya hay varios backtests guardados; el día uno basta con lanzar y leer uno |
| Gestión de invitados y permisos (UI) | El acceso a terceros es necesario y se cubre con el alta manual; la pantalla de administración puede esperar |

### Fuera de alcance (día uno)

| Funcionalidad | Por qué |
|---|---|
| Multi-workspace / espacios separados | Es una sola organización con un único espacio compartido. Varios espacios aislados no aportan nada ahora (ver nota al CTO) |
| Exportación de operaciones del backtest | Esbozada en el esqueleto pero sin terminar; no necesaria para validar el producto |
| Valoración / análisis ampliado | Aplazado explícitamente por negocio para iteraciones posteriores |

---

## Parte 3 — Ficha de atributos transversales

**Parte pública vs. login:** Todo tras login. Nada pensado para buscadores ni visible sin cuenta; herramienta para un grupo cerrado. Sin necesidades de SEO ni páginas públicas.

**Uso personal vs. multiusuario y roles:** Multiusuario con terceros invitados. Tres roles: **Administrador** (administra y da acceso), **Consulta+Backtest** (consulta y lanza backtests) y **Solo consulta** (solo consulta).

**Una organización o varias:** Una sola organización. **Un único espacio compartido** al que el administrador da acceso por invitación. Todos ven la misma realidad (misma selección semanal, mismos backtests). No hay separación de datos por usuario ni por cliente.

**Moneda:** La cartera se piensa y se reporta en **USD**. (Nota: el esqueleto asume EUR como base; cómo se maneja la conversión de tickers que cotizan en otra divisa —p. ej. canadienses— es detalle de Fase 1.)

**Dimensionamiento de cartera (backtest):** Equiponderación **1/N** entre las empresas seleccionadas cada semana. Requisito firme del día uno (no es solo herencia del motor).

**Procesos pesados, largos o programados:** Sí, dos. (a) Obtención de precios de mercado desde yfinance, lenta, candidata a segundo plano o ejecución programada. (b) Ejecución de backtests, cálculo que puede tardar y conviene lanzar sin bloquear al usuario. La Fase 1 debe prever trabajo asíncrono / en segundo plano.

**Integraciones con terceros:** Dos. **yfinance / Yahoo Finance** para precios de mercado (fuente no oficial: contar con que puede fallar o cambiar) y **Google** para inicio de sesión.

**Infraestructura de datos:** La base de datos es **PostgreSQL alojada en Railway**, poblada por el proceso externo de análisis. La app la consume directamente.

**Escala y restricciones:** Escala pequeña y conocida: grupo cerrado de usuarios, datos semanales (no alta frecuencia), universo de empresas USA / NASDAQ. No es producto de tráfico masivo. *Pendiente:* presupuesto, plazos y tamaño de equipo (no facilitados).

---

## Notas para la Fase 1 (decisiones de arquitectura, no de producto)

1. **Estructura multi-workspace:** el esqueleto trae arquitectura de varios espacios y crea uno automáticamente al registrar usuario. Producto ha decidido **un único espacio compartido**, así que la estructura multi-workspace debe simplificarse o reducirse a un solo espacio en uso.
2. **Moneda base USD:** el esqueleto asume EUR. Ajustar la base a USD y decidir cómo se convierte un ticker que cotiza en otra divisa (p. ej. dólares canadienses) cuando la cartera se reporta en USD.
3. **Fuente de precios:** yfinance "por ahora". Tener presente su fragilidad como fuente no oficial y la posibilidad de sustituirla.
4. **Base de datos en Railway:** PostgreSQL gestionada en Railway, ya poblada por el proceso externo. La app es consumidora de esos datos.

---

## Preguntas abiertas (pendientes de negocio)

1. **Plazos:** ¿hay una fecha objetivo para la primera versión en producción, o se desarrolla sin prisa?
2. **Presupuesto:** ¿hay un límite de gasto en infraestructura / servicios que la Fase 1 deba respetar?
3. **Equipo:** ¿lo desarrollas tú solo o hay más manos? Condiciona las decisiones de arquitectura.
