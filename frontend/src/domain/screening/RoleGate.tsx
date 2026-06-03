/**
 * `RoleGate` — oculta elementos según el rol (F3 §3.3, §1.4 M1).
 *
 * **Cosmético** — la autorización real vive en backend (F1 §5). Si el
 * usuario teclea la acción directa, el backend devuelve 403. `RoleGate`
 * solo ahorra al user ver un botón que no podría usar.
 *
 * Frontera vs guardián de rutas (F3 §1.4 M1):
 *   - `SessionGuard` (en `routes/`): rutas completas.
 *   - `RoleGate` (este): elementos dentro de una ruta ya permitida.
 *
 * Ejemplo:
 * ```tsx
 * <RoleGate allow={["analyst", "admin"]}>
 *   <Button>Lanzar backtest</Button>
 * </RoleGate>
 * ```
 */
import * as React from "react";

import { useAuth } from "@/app/session/auth-context";
import type { Role } from "@/lib/types";

export interface RoleGateProps {
  allow: Role[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGate({ allow, children, fallback = null }: RoleGateProps) {
  const { user } = useAuth();
  if (!user) return <>{fallback}</>;
  if (allow.includes(user.role)) return <>{children}</>;
  return <>{fallback}</>;
}
