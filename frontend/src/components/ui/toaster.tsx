/**
 * Toaster basado en `sonner` (F3 §3.3 inventario; M4 asignación de uso).
 *
 * Uso: importar `toast` desde `sonner` y montar `<Toaster />` una vez en
 * `app/App.tsx`.
 *
 * Casos de uso (F3 §3.3 M4):
 * - Confirmaciones no bloqueantes: `toast.success("Backtest en cola")`.
 * - Errores transitorios: `toast.error("Conexión interrumpida, reintentando")`.
 */
import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="top-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: "border border-border",
        },
      }}
    />
  );
}

export { toast } from "sonner";
