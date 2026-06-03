"""Servicio de dominio `BacktestEngine` (F2 §4.7, §4.9).

Orquesta el flujo del backtest:

1. **Resolver semanas**: del puerto `AnalysisReadPort` saca runs candidatos
   en el periodo; los pasa al `WeekResolver` (ADR-0004) para obtener
   `{Week → AnalysisRun}` con la regla "último OK gana".
2. **Reunir necesidades de precios**: para cada semana resuelta pide picks y
   acumula `(ticker, fecha_lunes)`.
3. **Calentamiento en lote**: una sola llamada `warm_up` al puerto (F2 §4.9).
   Si falla → backtest `failed` limpio antes de calcular nada.
4. **Rotación semana a semana**: invoca a la `RotationStrategy` con OHLC ya
   en caché. Atiende el `CancellationToken` entre semanas (F2 §6.5).
5. **Snapshot + resultado**: copia OHLC/FX usados; calcula equity de la
   cartera y un benchmark mínimo; marca el agregado COMPLETED.

Errores:
- Si el calentamiento falla → `Backtest.fail(error=prices_unavailable)`.
- Si se cancela en mitad → `Backtest.cancel(...)` y se sale del bucle.
- Si la base de análisis revela schema mismatch → ya saltó como excepción
  desde la ACL antes de llegar aquí; el engine la propaga.

Benchmark día uno: **buy-and-hold del capital inicial**, valor constante.
Es un placeholder honesto — el verdadero benchmark "equiponderado del
universo" / "índice externo" / "carteras aleatorias" requiere más datos
y se implementa en piezas posteriores. El contrato de `EquityPoint` ya
admite múltiples series, así que añadir más benchmarks no rompe nada.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.backtesting.backtest import Backtest, BacktestError
from app.domain.backtesting.parameters import BacktestStatus
from app.domain.backtesting.portfolio_position import PortfolioPosition
from app.domain.backtesting.ports import (
    AnalysisReadPort,
    CancellationToken,
    PriceProviderPort,
    PriceRequest,
    PriceUnavailableError,
)
from app.domain.backtesting.result import BacktestResult, EquityPoint, EquitySeries
from app.domain.backtesting.snapshot import (
    OHLC,
    ReproducibilitySnapshot,
    SnapshotPick,
    SnapshotWeek,
)
from app.domain.backtesting.strategy import RotationStrategy
from app.domain.screening.week_resolver import WeekResolver
from app.domain.shared.money import Money
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week

log = logging.getLogger(__name__)


class _NoCancellation:
    """`CancellationToken` por defecto que nunca cancela."""

    async def is_cancelled(self) -> bool:
        return False


@dataclass(slots=True)
class BacktestEngine:
    """Servicio puro. Recibe sus dependencias por inyección."""

    analysis: AnalysisReadPort
    prices: PriceProviderPort
    strategy: RotationStrategy

    async def run(
        self,
        backtest: Backtest,
        *,
        now: datetime,
        cancellation: CancellationToken | None = None,
    ) -> None:
        """Ejecuta el backtest. Muta `backtest` mediante sus transiciones.

        No persiste — eso es responsabilidad del worker (que llamará al
        repositorio antes y después de invocar `run`).
        """
        cancellation = cancellation or _NoCancellation()
        params = backtest.parameters

        # ────────── PASO 1: Resolver semanas ──────────
        try:
            runs = await self.analysis.list_runs_in_period(
                period_start_iso=str(params.period_start),
                period_end_iso=str(params.period_end),
            )
        except Exception as exc:
            backtest.fail(
                error=BacktestError(
                    code="analysis_unreachable",
                    message=f"Failed to read runs from analysis DB: {exc}",
                ),
                when=now,
            )
            log.exception("analysis_unreachable backtest_id=%s", backtest.id)
            return

        resolved = WeekResolver.resolve_weeks(runs)

        # Filtrar al periodo del backtest (el resolver puede haber devuelto
        # alguna semana adyacente si la ACL trajo runs cerca del borde).
        resolved_in_period = {
            w: run
            for w, run in resolved.items()
            if params.period_start.week_date <= w.week_date <= params.period_end.week_date
        }
        ordered_weeks = sorted(resolved_in_period.keys(), key=lambda w: w.week_date)

        backtest.start(when=now, weeks_total=len(ordered_weeks))

        if not ordered_weeks:
            # Caso límite: ningún run resuelto en el periodo → completar con
            # snapshot vacío y resultado vacío. No es failure: simplemente no
            # hay datos que validar.
            backtest.complete(
                result=BacktestResult(
                    total_return=Decimal("0"),
                    equity_curve=(
                        EquityPoint(EquitySeries.PORTFOLIO, params.period_start.week_date,
                                    params.initial_capital.amount),
                        EquityPoint(EquitySeries.BENCHMARK, params.period_start.week_date,
                                    params.initial_capital.amount),
                    ),
                ),
                snapshot=ReproducibilitySnapshot(weeks=()),
                when=now,
            )
            return

        # ────────── PASO 2: Reunir picks + necesidades de precios ──────────
        picks_by_week: dict[Week, set[TickerSymbol]] = {}
        for week in ordered_weeks:
            run = resolved_in_period[week]
            picks = await self.analysis.get_picks_for_run(run_id=run.id)
            picks_by_week[week] = {p.ticker for p in picks}

        # ────────── PASO 3: Calentamiento de caché en lote ──────────
        all_tickers: set[TickerSymbol] = set().union(*picks_by_week.values()) if picks_by_week else set()
        warm_requests = {
            PriceRequest(ticker=tk, day=week.week_date)
            for week in ordered_weeks
            for tk in (picks_by_week[week] | all_tickers)  # warm up todo el universo cada semana
        }
        try:
            await self.prices.warm_up(warm_requests)
        except PriceUnavailableError as exc:
            backtest.fail(
                error=BacktestError(
                    code="prices_unavailable",
                    message=str(exc),
                ),
                when=now,
            )
            log.warning("prices_unavailable backtest_id=%s err=%s", backtest.id, exc)
            return
        except Exception as exc:  # noqa: BLE001 — defensivo
            backtest.fail(
                error=BacktestError(
                    code="warm_up_failed",
                    message=f"Unexpected error during warm-up: {exc}",
                ),
                when=now,
            )
            log.exception("warm_up_failed backtest_id=%s", backtest.id)
            return

        # ────────── PASO 4: Rotación semana a semana ──────────
        positions: tuple[PortfolioPosition, ...] = ()
        cash: Money = params.initial_capital
        snapshot_weeks: list[SnapshotWeek] = []
        equity_portfolio: list[EquityPoint] = []
        equity_benchmark: list[EquityPoint] = []
        initial_amount = params.initial_capital.amount

        for idx, week in enumerate(ordered_weeks):
            if await cancellation.is_cancelled():
                # Caso A: endpoint ya marcó el bt cancelled en BBDD → in-memory
                # sigue running. Caso B: alguien llama al engine con un token
                # que cancela sin tocar el bt. En ambos: marcar terminal si no
                # lo está ya. `cancel()` es seguro mientras no sea terminal.
                if not backtest.status.is_terminal:
                    backtest.cancel(when=now)
                log.info("backtest_cancelled backtest_id=%s at week=%s", backtest.id, week)
                return

            target = frozenset(picks_by_week[week])

            ohlc_for_week: dict[TickerSymbol, OHLC] = {}
            for tk in target | {p.ticker for p in positions}:
                ohlc_for_week[tk] = await self.prices.get_ohlc(tk, week.week_date)

            rotation = self.strategy.rotate(
                current_positions=positions,
                target_tickers=target,
                ohlc=ohlc_for_week,
                cash=cash,
            )
            positions = rotation.positions
            cash = rotation.cash

            # Valor de cartera al CLOSE del lunes (en moneda base; sin FX día uno)
            portfolio_value = cash.amount
            for pos in positions:
                ohlc = ohlc_for_week[pos.ticker]
                portfolio_value += pos.shares * ohlc.close

            equity_portfolio.append(EquityPoint(
                EquitySeries.PORTFOLIO, week.week_date, portfolio_value.quantize(Decimal("0.01"))
            ))
            # Benchmark mínimo: buy-and-hold = constante = capital inicial.
            # Marcado en el código como placeholder honesto.
            equity_benchmark.append(EquityPoint(
                EquitySeries.BENCHMARK, week.week_date, initial_amount
            ))

            run = resolved_in_period[week]
            snapshot_picks = tuple(
                SnapshotPick(ticker=tk, ohlc=ohlc_for_week[tk]) for tk in sorted(target, key=lambda t: t.value)
            )
            snapshot_weeks.append(SnapshotWeek(
                week=week, resolved_run_id=run.id, run_code=run.run_code, picks=snapshot_picks
            ))

            backtest.record_progress(weeks_processed=idx + 1)

        # ────────── PASO 5: Construir resultado + completar ──────────
        final_value = equity_portfolio[-1].value if equity_portfolio else initial_amount
        total_return = ((final_value - initial_amount) / initial_amount).quantize(Decimal("0.0001"))

        result = BacktestResult(
            total_return=total_return,
            equity_curve=tuple(equity_portfolio) + tuple(equity_benchmark),
        )
        snapshot = ReproducibilitySnapshot(weeks=tuple(snapshot_weeks))

        backtest.complete(result=result, snapshot=snapshot, when=now)
