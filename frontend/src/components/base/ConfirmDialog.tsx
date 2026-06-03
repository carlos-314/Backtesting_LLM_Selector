/**
 * `ConfirmDialog` — confirmación genérica controlada (F3 §4.2).
 *
 * Controlado (no autónomo): el padre lleva `open`/`onOpenChange`. Cubre la
 * cancelación de backtest (F2 §6.5) con variante `destructive`.
 *
 * Contrato:
 *   ConfirmDialog {
 *     open: boolean; onOpenChange: (open: boolean) => void;
 *     title: string; description?: string;
 *     confirmLabel?: string;
 *     onConfirm: () => void;
 *     variant?: "default" | "destructive";
 *     isPending?: boolean;
 *   }
 *
 * Ejemplo:
 * ```tsx
 * <ConfirmDialog
 *   open={open}
 *   onOpenChange={setOpen}
 *   title="¿Cancelar este backtest?"
 *   description="Esta acción no se puede deshacer; el backtest pasará a estado 'cancelled'."
 *   confirmLabel="Sí, cancelar"
 *   variant="destructive"
 *   onConfirm={cancelMutation.mutate}
 *   isPending={cancelMutation.isPending}
 * />
 * ```
 */
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  variant?: "default" | "destructive";
  isPending?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  onConfirm,
  variant = "default",
  isPending,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={onConfirm}
            isLoading={isPending}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
