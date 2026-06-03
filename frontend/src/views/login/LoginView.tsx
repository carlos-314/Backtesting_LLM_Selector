/**
 * V-LOGIN — Login con Google Identity Services (F3 §1.3, §5.3).
 *
 * Tras éxito → navega al destino guardado o `/mapa`.
 * En 403 → navega a `/sin-acceso` (alta manual; "no estás en la lista").
 */
import { GoogleLogin } from "@react-oauth/google";
import { Navigate, useNavigate } from "@tanstack/react-router";
import * as React from "react";

import { useAuth } from "@/app/session/auth-context";
import { ErrorState } from "@/components/base/ErrorState";
import { ApiError } from "@/lib/api-error";

export function LoginView() {
  const { user, signIn, isReady } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = React.useState<ApiError | null>(null);
  const [isPending, setIsPending] = React.useState(false);

  // Si ya hay sesión, redirige (F3 §5.3 edge: ya logueado → /mapa)
  if (isReady && user) {
    return <Navigate to="/mapa" replace />;
  }

  const handleSuccess = async (credential: string) => {
    setError(null);
    setIsPending(true);
    try {
      await signIn(credential);
      void navigate({ to: "/mapa", replace: true });
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e);
        if (e.status === 403) {
          void navigate({ to: "/sin-acceso", replace: true });
        }
      } else {
        setError(
          new ApiError(500, "internal_error", "Error inesperado durante el login"),
        );
      }
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-8">
      <div className="w-full max-w-sm space-y-6 rounded-lg border bg-card p-6 shadow-sm">
        <header className="space-y-1 text-center">
          <h1 className="text-xl font-semibold tracking-tight">
            Backtesting LLM Selector
          </h1>
          <p className="text-sm text-muted-foreground">
            Inicia sesión con tu cuenta de Google.
          </p>
        </header>

        <div className="flex justify-center" aria-busy={isPending}>
          <GoogleLogin
            onSuccess={(resp) => {
              if (resp.credential) void handleSuccess(resp.credential);
              else
                setError(
                  new ApiError(
                    401,
                    "invalid_google_token",
                    "Google no devolvió un id_token",
                  ),
                );
            }}
            onError={() =>
              setError(
                new ApiError(502, "google_unreachable", "Google no respondió"),
              )
            }
            useOneTap={false}
            text="signin_with"
            shape="rectangular"
            theme="outline"
          />
        </div>

        {error && error.status !== 403 && (
          <div className="text-sm">
            <ErrorState error={error} />
          </div>
        )}
      </div>
    </div>
  );
}
