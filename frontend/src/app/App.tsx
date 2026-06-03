/**
 * App raíz: provider tree (F3 §6.1).
 *
 * Orden:
 *  - QueryClientProvider — capa de servidor (cache, polling).
 *  - GoogleOAuthProvider — Google Identity Services para `LoginView`.
 *  - AuthProvider — sesión propia (Bearer en memoria, ADR-0007).
 *  - RouterProvider — árbol de rutas.
 *  - Toaster — sonner.
 */
import { GoogleOAuthProvider } from "@react-oauth/google";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import { AuthProvider } from "@/app/session/auth-context";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toaster";
import { ApiError } from "@/lib/api-error";
import { router } from "@/routes/routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      // F3 §6.5: no reintentar 401/403/404; backoff suave para los demás
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if ([401, 403, 404, 409, 422].includes(error.status)) return false;
        }
        return failureCount < 2;
      },
    },
  },
});

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <AuthProvider>
          <TooltipProvider delayDuration={300}>
            <RouterProvider router={router} />
            <Toaster />
          </TooltipProvider>
        </AuthProvider>
      </GoogleOAuthProvider>
    </QueryClientProvider>
  );
}
