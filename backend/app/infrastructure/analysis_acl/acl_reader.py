"""Implementación de `AnalysisReadPort` y `ScreeningReadPort` sobre la BBDD
legacy (F2 §4.4, §4.8).

Capa anticorrupción (ACL): traduce el casing sucio del schema externo a los
read-models limpios del dominio. Es el ÚNICO sitio del backend donde se
acepta convivir con `"fechaRun"`, `"Ticker"`, etc.

SQL crudo (no ORM): la base es ajena y de solo lectura; modelarla con ORM
acoplaría nuestro código a un schema que no controlamos.

Validación defensiva: al primer uso por instancia, valida el schema mínimo
(analysis_runs + portfolios) y cachea el resultado. Las tablas más anchas
(`processed_stocks`, `stock`) se consultan con tolerancia a columnas
ausentes: si la columna no existe, el campo del read-model queda en `None`.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.screening.read_models import AnalysisRun, Pick
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week
from app.infrastructure.analysis_acl.schema_validator import validate_analysis_schema


class AnalysisAclReader:
    """Implementación del `AnalysisReadPort` (F2 §4.8) sobre la BBDD legacy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._schema_validated = False

    async def _ensure_schema(self) -> None:
        if self._schema_validated:
            return
        await validate_analysis_schema(self._session)
        self._schema_validated = True

    async def list_runs_in_period(
        self, *, period_start_iso: str, period_end_iso: str
    ) -> list[AnalysisRun]:
        """Lista runs cuya `fechaRun` cae en [start, end] semanas (NY).

        Args:
            period_start_iso: `YYYY-MM-DD` del primer lunes (canónico NY).
            period_end_iso: `YYYY-MM-DD` del último lunes (canónico NY).

        El rango se traduce a un intervalo half-open en UTC:
            [lunes_NY_start.start_ny, lunes_NY_end.next().start_ny)
        Esto incluye todos los instantes de las semanas del periodo.
        """
        await self._ensure_schema()

        start_week = Week.from_iso(period_start_iso)
        end_week = Week.from_iso(period_end_iso)
        start_instant = start_week.start_ny
        end_instant_exclusive = end_week.next().start_ny

        # LEFT JOIN para precomputar pick_count sin N+1 al cargar runs.
        # COUNT(*) cuenta NULLs como 0 gracias a LEFT JOIN + COALESCE.
        sql = text("""
            SELECT
                r.id_run                  AS id_run,
                r."fechaRun"              AS fecha_run,
                r.run_code                AS run_code,
                r.status                  AS status,
                COALESCE(picks.cnt, 0)    AS pick_count
            FROM analysis_runs r
            LEFT JOIN (
                SELECT id_run, COUNT(*) AS cnt
                FROM portfolios
                WHERE ticker IS NOT NULL
                GROUP BY id_run
            ) picks ON picks.id_run = r.id_run
            WHERE r."fechaRun" >= :start
              AND r."fechaRun" < :end
            ORDER BY r."fechaRun" ASC, r.id_run ASC
        """)
        result = await self._session.execute(
            sql, {"start": start_instant, "end": end_instant_exclusive}
        )
        return [
            AnalysisRun(
                id=row.id_run,
                fecha_run=row.fecha_run,
                run_code=row.run_code,
                status=row.status,
                pick_count=row.pick_count,
            )
            for row in result
        ]

    async def get_picks_for_run(self, *, run_id: int) -> list[Pick]:
        """Picks (`portfolios`) de un run. Filtra tickers NULL/vacíos."""
        await self._ensure_schema()

        sql = text("""
            SELECT ticker, nombre, rol
            FROM portfolios
            WHERE id_run = :run_id
              AND ticker IS NOT NULL
              AND TRIM(ticker) <> ''
            ORDER BY id_portfolio ASC
        """)
        result = await self._session.execute(sql, {"run_id": run_id})
        picks: list[Pick] = []
        for row in result:
            # `TickerSymbol.of` normaliza (uppercase + trim).
            picks.append(
                Pick(
                    ticker=TickerSymbol.of(row.ticker),
                    role=row.rol,
                    nombre=row.nombre,
                )
            )
        return picks

    # ════════════════════════ ScreeningReadPort ════════════════════════

    async def get_company_data(
        self, *, run_id: int, ticker: TickerSymbol
    ) -> dict[str, Any] | None:
        """Detalle de una empresa de un run (F2 §6.4).

        Día uno devuelve el row de `processed_stocks` casi en bruto (mapeo
        mínimo de casing). El catálogo definitivo está pendiente de ADR-0002
        (R2-bis); la API lo expone tal cual desde la capa de aplicación.
        """
        await self._ensure_schema()
        sql = text("""
            SELECT to_jsonb(ps.*) AS raw
            FROM processed_stocks ps
            WHERE ps.id_run = :run_id AND ps."Ticker" = :ticker
            LIMIT 1
        """)
        row = (await self._session.execute(
            sql, {"run_id": run_id, "ticker": str(ticker)}
        )).scalar_one_or_none()
        return row  # JSONB → dict

    async def list_universe_for_run(self, *, run_id: int) -> list[TickerSymbol]:
        """Tickers analizados (universo) del run, para la matriz (ADR-0001)."""
        await self._ensure_schema()
        sql = text("""
            SELECT DISTINCT "Ticker"
            FROM processed_stocks
            WHERE id_run = :run_id
              AND "Ticker" IS NOT NULL
              AND TRIM("Ticker") <> ''
            ORDER BY "Ticker"
        """)
        result = await self._session.execute(sql, {"run_id": run_id})
        return [TickerSymbol.of(row[0]) for row in result.all()]

    async def get_companies_metadata(
        self, *, tickers: list[TickerSymbol]
    ) -> dict[TickerSymbol, dict[str, Any]]:
        """Metadata (nombre, país, currency) desde `stock` para los tickers
        dados. Tolera tickers no presentes en `stock` (devuelve dict vacío)."""
        await self._ensure_schema()
        if not tickers:
            return {}
        ticker_strs = [str(t) for t in tickers]
        sql = text("""
            SELECT ticker, nombre, pais, currency, exchange
            FROM stock
            WHERE ticker = ANY(:tickers)
        """)
        result = await self._session.execute(sql, {"tickers": ticker_strs})
        out: dict[TickerSymbol, dict[str, Any]] = {}
        for row in result:
            ts = TickerSymbol.of(row.ticker)
            out[ts] = {
                "name": row.nombre,
                "country": row.pais,
                "currency": row.currency,
                "exchange": row.exchange,
            }
        return out

    async def list_companies_summary_for_run(
        self, *, run_id: int, limit: int, after_ticker: str | None
    ) -> list[dict[str, Any]]:
        """Lista paginada (por ticker ASC) de empresas analizadas en un run,
        con metadata básica. Usado por `GET /weeks/{w}/companies`.

        La paginación es por cursor de `ticker`: la siguiente página empieza
        en `ticker > after_ticker`. Sin filtros/sort día uno (ADR-0003
        propuesta, no aceptada todavía).
        """
        await self._ensure_schema()
        sql = text("""
            SELECT
                ps."Ticker" AS ticker,
                ps."Nom" AS name,
                ps."Country" AS country,
                ps."Exchange" AS exchange,
                ps."StockCurrency" AS currency,
                EXISTS (
                    SELECT 1 FROM portfolios p
                    WHERE p.id_run = ps.id_run AND p.ticker = ps."Ticker"
                ) AS in_portfolio
            FROM processed_stocks ps
            WHERE ps.id_run = :run_id
              AND ps."Ticker" IS NOT NULL
              AND TRIM(ps."Ticker") <> ''
              AND ps."Ticker" > COALESCE(:after_ticker, '')
            ORDER BY ps."Ticker" ASC
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql,
            {"run_id": run_id, "limit": limit, "after_ticker": after_ticker},
        )
        return [
            {
                "ticker": str(TickerSymbol.of(row.ticker)),
                "name": row.name,
                "country": row.country,
                "exchange": row.exchange,
                "currency": row.currency,
                "in_portfolio": bool(row.in_portfolio),
            }
            for row in result
        ]
