/**
 * Guardián de sesión (F3 §1.4).
 *
 * - Si no hay user → `/login`.
 * - Si la ruta exige un rol y el user no lo tiene → redirige a `/mapa`.
 *   (La autorización real está en backend F1 §5; este guardián es cosmético).
 *
 * `RoleGate` (F3 §1.4 M1) vive aparte, en `domain/`; gobierna elementos,
 * no rutas.
 */
import * as React from "react";
import { Navigate } from "@tanstack/react-router";

import { useAuth } from "@/app/session/auth-context";
import { Skeleton } from "@/components/ui/skeleton";
import type { Role } from "@/lib/types";

interface Props {
  children: React.ReactNode;
  requireRole?: Role;
}

export function SessionGuard({ children, requireRole }: Props) {
  const { user, isReady } = useAuth();

  if (!isReady) {
    // F3 §5.2 — splash mínimo, nunca pantalla en blanco ni flash de login
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="mx-auto max-w-7xl space-y-3">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (user == null) {
    return <Navigate to="/login" replace />;
  }

  if (requireRole && user.role !== requireRole && user.role !== "admin") {
    // admin tiene todas las capacidades (F0/F3 §5.5)
    return <Navigate to="/mapa" replace />;
  }

  return <>{children}</>;
}
