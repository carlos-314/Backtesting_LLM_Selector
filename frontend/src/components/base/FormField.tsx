/**
 * `FormField` — label + control + error + ayuda (F3 §4.2).
 *
 * `label` y `htmlFor` son OBLIGATORIOS para no perder la asociación al
 * envolver primitivos Radix; `aria-describedby` se cablea automáticamente
 * (F3 §8 accesibilidad).
 *
 * Contrato:
 *   FormField {
 *     label: string;          // obligatoria (accesibilidad)
 *     htmlFor: string;        // obligatoria — liga label↔control
 *     children: ReactNode;    // el control
 *     error?: string;
 *     hint?: string;
 *     required?: boolean;
 *   }
 *
 * El control hijo debe tener `id={htmlFor}` y aceptar `aria-invalid` y
 * `aria-describedby`. Si quieres usarlo con `Input` de shadcn, basta:
 *
 * ```tsx
 * <FormField label="Nombre" htmlFor="bt-name" error={errors.name?.message}>
 *   <Input
 *     id="bt-name"
 *     aria-invalid={!!errors.name}
 *     aria-describedby={errors.name ? "bt-name-error" : undefined}
 *     {...register("name")}
 *   />
 * </FormField>
 * ```
 */
import * as React from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface FormFieldProps {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
  error?: string;
  hint?: string;
  required?: boolean;
  className?: string;
}

export function FormField({
  label,
  htmlFor,
  children,
  error,
  hint,
  required,
  className,
}: FormFieldProps) {
  const errorId = `${htmlFor}-error`;
  const hintId = `${htmlFor}-hint`;

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor} className="flex items-center gap-1">
        <span>{label}</span>
        {required && (
          <span aria-label="campo obligatorio" className="text-destructive">
            *
          </span>
        )}
      </Label>
      {children}
      {hint && !error && (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p
          id={errorId}
          role="alert"
          aria-live="polite"
          className="text-xs text-destructive"
        >
          {error}
        </p>
      )}
    </div>
  );
}
