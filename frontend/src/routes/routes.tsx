/**
 * Árbol de rutas (F3 §1.4).
 *
 *   /  (raíz)
 *   ├─ /login                     V-LOGIN
 *   ├─ /sin-acceso                V-ACCESO-DENEGADO
 *   └─ (guardián de sesión)
 *      ├─ /                       → /mapa
 *      ├─ /mapa                   V-MATRIX
 *      ├─ /mapa/:semana/:ticker   V-COMPANY
 *      ├─ /backtests              V-BT-LISTA
 *      ├─ /backtests/nuevo        V-BT-LANZAR  (solo analyst)
 *      ├─ /backtests/:id          V-BT-RESULTADO
 *      ├─ /backtests/comparar     V-BT-COMPARAR (pospuesta — ruta prevista)
 *      ├─ /admin                  (pospuesta — solo admin)
 *      └─ *                       404 interna
 */
import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  Navigate,
} from "@tanstack/react-router";

import { AppShell } from "@/app/shell";
import { SessionGuard } from "@/routes/session-guard";

import { LoginView } from "@/views/login/LoginView";
import { AccessDeniedView } from "@/views/access-denied/AccessDeniedView";
import { MatrixView } from "@/views/matrix/MatrixView";
import { CompanyView } from "@/views/company/CompanyView";
import { BacktestsListView } from "@/views/backtests-list/BacktestsListView";
import { BacktestNewView } from "@/views/backtest-new/BacktestNewView";
import { BacktestResultView } from "@/views/backtest-result/BacktestResultView";
import { NotFoundView } from "@/views/not-found/NotFoundView";
import { ExamplesView } from "@/views/__examples/ExamplesView";

// ─────────────────────── árbol ───────────────────────

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginView,
});

const accessDeniedRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sin-acceso",
  component: AccessDeniedView,
});

// /__examples — galería interna de componentes base (sin guardián).
// No es UI de producto; sirve para QA visual de los componentes del estrato 2.
const examplesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/__examples",
  component: ExamplesView,
});

// Rutas autenticadas envueltas en AppShell + SessionGuard.
const authedRoot = createRoute({
  getParentRoute: () => rootRoute,
  id: "_authed",
  component: () => (
    <SessionGuard>
      <AppShell />
    </SessionGuard>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/",
  component: () => <Navigate to="/mapa" replace />,
});

const matrixRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/mapa",
  component: MatrixView,
});

const companyRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/mapa/$semana/$ticker",
  component: CompanyView,
});

const backtestsListRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/backtests",
  component: BacktestsListView,
});

const backtestNewRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/backtests/nuevo",
  component: () => (
    <SessionGuard requireRole="analyst">
      <BacktestNewView />
    </SessionGuard>
  ),
});

const backtestResultRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/backtests/$id",
  component: BacktestResultView,
});

const backtestCompareRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/backtests/comparar",
  component: () => (
    <PlaceholderPosposed name="V-BT-COMPARAR" />
  ),
});

const adminRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "/admin",
  component: () => (
    <SessionGuard requireRole="admin">
      <PlaceholderPosposed name="V-ADMIN-INVITADOS" />
    </SessionGuard>
  ),
});

const notFoundRoute = createRoute({
  getParentRoute: () => authedRoot,
  path: "$",
  component: NotFoundView,
});

function PlaceholderPosposed({ name }: { name: string }) {
  return (
    <div className="rounded-md border border-dashed p-12 text-center">
      <h1 className="text-lg font-semibold">{name}</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Vista pospuesta día uno (F3 §1.3).
      </p>
    </div>
  );
}

const routeTree = rootRoute.addChildren([
  loginRoute,
  accessDeniedRoute,
  examplesRoute,
  authedRoot.addChildren([
    indexRoute,
    matrixRoute,
    companyRoute,
    backtestsListRoute,
    backtestNewRoute,
    backtestResultRoute,
    backtestCompareRoute,
    adminRoute,
    notFoundRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
