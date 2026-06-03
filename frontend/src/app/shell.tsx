/**
 * AppShell — layout con navegación persistente (F3 §3.3, §1.4).
 *
 * Items de la navegación los filtra el componente según el rol (F3 §1.4
 * "RoleGate cosmético"; la autorización real vive en backend, F1 §5).
 */
import { Link, Outlet, useLocation } from "@tanstack/react-router";
import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/app/session/auth-context";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  to: string;
  rolesAllowed?: ("viewer" | "analyst" | "admin")[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Mapa", to: "/mapa" },
  { label: "Backtests", to: "/backtests" },
  // Admin se muestra solo a `admin`; la pantalla real está pospuesta (F3 §1.2).
  { label: "Admin", to: "/admin", rolesAllowed: ["admin"] },
];

export function AppShell() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();

  const visibleItems = NAV_ITEMS.filter(
    (it) => !it.rolesAllowed || (user && it.rolesAllowed.includes(user.role)),
  );

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <nav
          aria-label="Navegación principal"
          className="container mx-auto flex h-14 max-w-7xl items-center justify-between px-4"
        >
          <div className="flex items-center gap-6">
            <Link to="/mapa" className="text-sm font-semibold tracking-tight">
              Backtesting LLM Selector
            </Link>
            <ul className="flex items-center gap-2">
              {visibleItems.map((it) => {
                const active = pathname.startsWith(it.to);
                return (
                  <li key={it.to}>
                    <Link
                      to={it.to}
                      className={cn(
                        "rounded-md px-3 py-1.5 text-sm transition-colors",
                        active
                          ? "bg-muted text-foreground"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      {it.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="flex items-center gap-3">
            {user && (
              <>
                <span className="text-sm text-muted-foreground" aria-live="polite">
                  {user.full_name ?? user.email}
                </span>
                <Separator orientation="vertical" className="h-5" />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void signOut()}
                  aria-label="Cerrar sesión"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Salir</span>
                </Button>
              </>
            )}
          </div>
        </nav>
      </header>
      <main className="container mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
