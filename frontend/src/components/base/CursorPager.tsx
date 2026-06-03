/**
 * `CursorPager` — patrón "cargar más" sobre cursor opaco (F3 §4.2, F2 §6.1).
 *
 * NO ve el cursor: vive en el hook de la vista y el caller decide cuándo
 * llamar a `onLoadMore`. El componente solo dibuja el botón con sus estados.
 *
 * Contrato:
 *   CursorPager {
 *     hasMore: boolean;
 *     isLoadingMore?: boolean;
 *     onLoadMore: () => void;
 *   }
 *
 * Ejemplo:
 * ```tsx
 * const query = useInfiniteBacktestsQuery();
 * <CursorPager
 *   hasMore={!!query.hasNextPage}
 *   isLoadingMore={query.isFetchingNextPage}
 *   onLoadMore={() => query.fetchNextPage()}
 * />
 * ```
 */
import { Button } from "@/components/ui/button";

export interface CursorPagerProps {
  hasMore: boolean;
  isLoadingMore?: boolean;
  onLoadMore: () => void;
}

export function CursorPager({ hasMore, isLoadingMore, onLoadMore }: CursorPagerProps) {
  if (!hasMore) return null;
  return (
    <div className="flex justify-center py-4">
      <Button
        variant="outline"
        onClick={onLoadMore}
        isLoading={isLoadingMore}
        aria-label="Cargar más resultados"
      >
        Cargar más
      </Button>
    </div>
  );
}
