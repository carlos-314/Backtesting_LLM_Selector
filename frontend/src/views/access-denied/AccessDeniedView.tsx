/** V-ACCESO-DENEGADO — placeholder (B1). */
export function AccessDeniedView() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-8">
      <div className="w-full max-w-md rounded-lg border bg-card p-6 text-center shadow-sm">
        <h1 className="text-lg font-semibold">V-ACCESO-DENEGADO</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Tu email no está autorizado. Pide al administrador que te dé de alta.
        </p>
      </div>
    </div>
  );
}
