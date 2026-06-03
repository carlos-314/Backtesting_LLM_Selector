import {
  createRouter,
  createRoute,
  createRootRoute,
  RouterProvider,
  Outlet,
  Navigate,
} from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { useAuthStore } from '@/stores/auth-store';
import { LoginPage } from '@/pages/login';
import { WorkspacesPage } from '@/pages/workspaces';
import { DashboardPage } from '@/pages/dashboard';
import { UploadPage } from '@/pages/upload';
import { SignalsPage } from '@/pages/signals';
import { BacktestNewPage } from '@/pages/backtest-new';
import { BacktestResultsPage } from '@/pages/backtest-results';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: (failureCount, error: any) => {
        if (error?.status === 401 || error?.status === 403 || error?.status === 404) return false;
        return failureCount < 2;
      },
    },
  },
});

// Routes
const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => {
    const token = useAuthStore.getState().token;
    return token ? <Navigate to="/workspaces" /> : <Navigate to="/login" />;
  },
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
});

const workspacesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspaces',
  component: () => {
    const token = useAuthStore.getState().token;
    if (!token) return <Navigate to="/login" />;
    return <WorkspacesPage />;
  },
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspaces/$workspaceId',
  component: () => {
    const token = useAuthStore.getState().token;
    if (!token) return <Navigate to="/login" />;
    return <DashboardPage />;
  },
});

const uploadRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspaces/$workspaceId/upload',
  component: () => {
    const token = useAuthStore.getState().token;
    if (!token) return <Navigate to="/login" />;
    return <UploadPage />;
  },
});

const signalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspaces/$workspaceId/signals',
  component: () => {
    const token = useAuthStore.getState().token;
    if (!token) return <Navigate to="/login" />;
    return <SignalsPage />;
  },
});

const backtestNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspaces/$workspaceId/backtest/new',
  component: () => {
    const token = useAuthStore.getState().token;
    if (!token) return <Navigate to="/login" />;
    return <BacktestNewPage />;
  },
});

const backtestResultsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspaces/$workspaceId/backtest/run/$backtestId',
  component: () => {
    const token = useAuthStore.getState().token;
    if (!token) return <Navigate to="/login" />;
    return <BacktestResultsPage />;
  },
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  workspacesRoute,
  dashboardRoute,
  uploadRoute,
  signalsRoute,
  backtestNewRoute,
  backtestResultsRoute,
]);

const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

export default function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </GoogleOAuthProvider>
  );
}
