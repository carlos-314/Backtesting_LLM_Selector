/**
 * `ErrorState` — error mostrable al usuario (F3 §4.2, §5.1).
 *
 * Convierte el `ApiError` (shape uniforme F2 §6.1) en un mensaje legible.
 * NO muestra `details` ni `context` (eso es para logs, F3 §4.2).
 *
 * Mapeo de `code` → texto en español. Cualquier código no listado cae al
 * mensaje genérico del propio error.
 *
 * Contrato:
 *   ErrorState { error: ApiError; onRetry?: () => void; }
 *
 * Ejemplo:
 * ```tsx
 * <ErrorState error={apiErr} onRetry={() => query.refetch()} />
 * ```
 */
import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/api-error";

const MESSAGES: Record<string, string> = {
  // Análisis
  analysis_unreachable: "La base de análisis no responde. Vuelve a intentarlo en unos minutos.",
  analysis_schema_mismatch:
    "Detectamos una incompatibilidad en la base de análisis. El equipo técnico ya está avisado.",

  // Auth
  invalid_google_token: "El token de Google no es válido. Vuelve a iniciar sesión.",
  user_not_authorized: "Tu email no está autorizado. Pide al administrador que te dé de alta.",
  google_unreachable: "Google no está disponible ahora mismo. Reintenta en unos segundos.",

  // Backtests
  backtest_not_permitted: "Tu rol no permite lanzar backtests.",
  invalid_period: "El periodo solicitado no es válido.",
  invalid_capital: "El capital inicial debe ser un número positivo.",
  backtest_not_found: "El backtest solicitado no existe.",
  backtest_not_ready: "El backtest aún no está listo. Espera a que termine.",
  not_cancellable: "Este backtest ya no se puede cancelar.",

  // Comunes
  not_found: "El recurso solicitado no existe.",
  forbidden: "No tienes permiso para esta operación.",
  unauthorized: "Tu sesión ha expirado. Inicia sesión de nuevo.",
  bad_gateway: "Servicio no disponible ahora mismo.",
  service_unavailable: "Servicio no disponible ahora mismo.",
  internal_error: "Ha ocurrido un error inesperado.",
};

export interface ErrorStateProps {
  error: ApiError | { code: string; message: string };
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const displayMessage = MESSAGES[error.code] ?? error.message;

  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-12 text-center"
    >
      <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden="true" />
      <h2 className="text-base font-semibold text-foreground">{displayMessage}</h2>
      <p className="text-xs text-muted-foreground" aria-label="Código de error">
        Código: <code className="font-mono">{error.code}</code>
      </p>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="mt-2"
        >
          <RefreshCw className="h-4 w-4" />
          Reintentar
        </Button>
      )}
    </div>
  );
}
