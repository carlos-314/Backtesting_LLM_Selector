/**
 * Contexto de sesión (F3 §5.2 estado de arranque, §6.1).
 *
 * - Resuelve la sesión al arrancar: ¿hay token previo? Si no, sigue sin sesión.
 *   Día uno el token vive solo en memoria (ADR-0007); recargas pierden la
 *   sesión. Si en el futuro se quiere persistir, hay que decidir el medio
 *   (sessionStorage vs cookies HTTPOnly) con un ADR.
 * - Expone `useAuth()` con: user, isReady, signIn(idToken), signOut().
 * - El cliente API lee el token via `configureAuth()` del lib.
 */
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { apiFetch, configureAuth } from "@/lib/api-client";
import type { LoginResponse, SessionUser } from "@/lib/types";

interface AuthContextValue {
  user: SessionUser | null;
  /** `false` mientras la sesión se está resolviendo al arrancar. */
  isReady: boolean;
  signIn: (googleIdToken: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<SessionUser | null>(null);
  const [token, setToken] = React.useState<string | null>(null);
  const [isReady, setIsReady] = React.useState(false);
  const qc = useQueryClient();

  // Configurar el cliente API para que lea el token de este estado.
  // En 401 transversal (F3 §6.3 C5) limpiamos sesión y query cache.
  React.useEffect(() => {
    configureAuth(
      () => token,
      () => {
        setToken(null);
        setUser(null);
        qc.clear();
      },
    );
  }, [token, qc]);

  // F3 §5.2 estado de arranque. Día uno no se persiste el token (ADR-0007),
  // así que tras configureAuth, marcamos ready inmediatamente.
  React.useEffect(() => {
    setIsReady(true);
  }, []);

  const signIn = React.useCallback(
    async (googleIdToken: string) => {
      const res = await apiFetch<LoginResponse>("/api/v1/auth/google", {
        method: "POST",
        body: { id_token: googleIdToken },
      });
      setToken(res.access_token);
      setUser(res.user);
    },
    [],
  );

  const signOut = React.useCallback(async () => {
    try {
      // Intento server-side (204). Si falla, ignoramos: stateless de todos
      // modos (ADR-0007).
      if (token) {
        await apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
      }
    } catch {
      // intencionado
    } finally {
      setToken(null);
      setUser(null);
      // F3 §6.4: logout invalida TODO el estado de servidor.
      qc.clear();
    }
  }, [qc, token]);

  const value = React.useMemo<AuthContextValue>(
    () => ({ user, isReady, signIn, signOut }),
    [user, isReady, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (ctx == null) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
