/** Vista 404 interna (F3 §1.4). */
import { Link } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";

export function NotFoundView() {
  return (
    <div className="rounded-md border border-dashed p-12 text-center">
      <h1 className="text-lg font-semibold">No encontrado</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        La ruta solicitada no existe en esta aplicación.
      </p>
      <div className="mt-4">
        <Button asChild variant="outline">
          <Link to="/mapa">Volver al mapa</Link>
        </Button>
      </div>
    </div>
  );
}
