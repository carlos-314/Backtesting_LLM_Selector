"""Implementación de `BacktestRepositoryPort` (F2 §4.8, §5.2, §5.3).

Persiste el agregado `Backtest` completo (raíz + result + equity curve +
snapshot week + snapshot pick) en una sola transacción. La idempotencia se
garantiza así:

- `backtest` (raíz): UPSERT por `id`.
- `backtest_result`, `backtest_equity_point`, `backtest_snapshot_week`,
  `backtest_snapshot_pick`: DELETE existentes por `backtest_id` antes del
  INSERT (CASCADE de snapshot_week → snapshot_pick).

El mapeo periodo→DATERANGE usa `Range(start_monday, end_monday, bounds="[]")`;
Postgres normaliza a `[lower, upper+1day)` al persistir.

`get` reconstruye el agregado con `Backtest.rehydrate()` (no re-ejecuta
transiciones).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.backtesting.backtest import Backtest, BacktestError
from app.domain.backtesting.parameters import (
    BacktestId,
    BacktestParameters,
    BacktestStatus,
)
from app.domain.backtesting.result import BacktestResult, EquityPoint, EquitySeries
from app.domain.backtesting.snapshot import (
    OHLC,
    ReproducibilitySnapshot,
    SnapshotPick,
    SnapshotWeek,
)
from app.domain.shared.money import Money
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week
from app.infrastructure.persistence.models.backtest import (
    Backtest as BacktestModel,
)
from app.infrastructure.persistence.models.backtest import (
    BacktestEquityPoint as EquityPointModel,
)
from app.infrastructure.persistence.models.backtest import (
    BacktestResult as ResultModel,
)
from app.infrastructure.persistence.models.snapshot import (
    BacktestSnapshotPick as PickModel,
)
from app.infrastructure.persistence.models.snapshot import (
    BacktestSnapshotWeek as WeekModel,
)


class BacktestRepository:
    """Implementación de `BacktestRepositoryPort` sobre Postgres + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ─────────────────────────── save ───────────────────────────

    async def save(self, backtest: Backtest) -> None:
        await self._upsert_root(backtest)
        # Limpia dependientes para mantener idempotencia (CASCADE en snapshot_pick).
        await self._session.execute(
            delete(ResultModel).where(ResultModel.backtest_id == backtest.id)
        )
        await self._session.execute(
            delete(EquityPointModel).where(EquityPointModel.backtest_id == backtest.id)
        )
        await self._session.execute(
            delete(WeekModel).where(WeekModel.backtest_id == backtest.id)
        )
        if backtest.status == BacktestStatus.COMPLETED:
            assert backtest.result is not None and backtest.snapshot is not None
            await self._insert_result(backtest)
            await self._insert_equity(backtest)
            await self._insert_snapshot(backtest)
        await self._session.commit()

    async def _upsert_root(self, bt: Backtest) -> None:
        period = Range(
            bt.parameters.period_start.week_date,
            bt.parameters.period_end.week_date,
            bounds="[]",
        )
        error_detail = None
        if bt.error is not None:
            error_detail = {
                "code": bt.error.code,
                "message": bt.error.message,
                "context": bt.error.context,
            }
        values = {
            "id": bt.id,
            "created_by": bt.created_by,
            "name": bt.name,
            "status": bt.status.value,
            "period": period,
            "initial_capital": bt.parameters.initial_capital.amount,
            "base_currency": bt.parameters.base_currency,
            "strategy_code": bt.parameters.strategy_code,
            "benchmark_code": bt.parameters.benchmark_code,
            "weeks_total": bt.weeks_total,
            "weeks_processed": bt.weeks_processed,
            "error_detail": error_detail,
            "created_at": bt.created_at,
            "started_at": bt.started_at,
            "completed_at": bt.completed_at,
        }
        stmt = insert(BacktestModel).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "status": stmt.excluded.status,
                "weeks_total": stmt.excluded.weeks_total,
                "weeks_processed": stmt.excluded.weeks_processed,
                "error_detail": stmt.excluded.error_detail,
                "started_at": stmt.excluded.started_at,
                "completed_at": stmt.excluded.completed_at,
            },
        )
        await self._session.execute(stmt)

    async def _insert_result(self, bt: Backtest) -> None:
        r = bt.result
        assert r is not None
        await self._session.execute(
            insert(ResultModel).values(
                backtest_id=bt.id,
                total_return=r.total_return,
                cagr=r.cagr,
                volatility=r.volatility,
                sharpe=r.sharpe,
                max_drawdown=r.max_drawdown,
                metrics_extra=r.metrics_extra,
            )
        )

    async def _insert_equity(self, bt: Backtest) -> None:
        r = bt.result
        assert r is not None
        if not r.equity_curve:
            return
        values = [
            {
                "backtest_id": bt.id,
                "series": pt.series.value,
                "point_date": pt.point_date,
                "value": pt.value,
            }
            for pt in r.equity_curve
        ]
        await self._session.execute(insert(EquityPointModel).values(values))

    async def _insert_snapshot(self, bt: Backtest) -> None:
        s = bt.snapshot
        assert s is not None
        if not s.weeks:
            return
        for sw in s.weeks:
            week_model = WeekModel(
                backtest_id=bt.id,
                week_date=sw.week.week_date,
                resolved_run_id=sw.resolved_run_id,
                run_code=sw.run_code,
            )
            self._session.add(week_model)
            await self._session.flush()  # genera week_model.id
            if sw.picks:
                pick_values = [
                    {
                        "snapshot_week_id": week_model.id,
                        "ticker": str(p.ticker),
                        "open": p.ohlc.open,
                        "high": p.ohlc.high,
                        "low": p.ohlc.low,
                        "close": p.ohlc.close,
                        "fx_pair": p.fx_pair,
                        "fx_rate": p.fx_rate,
                    }
                    for p in sw.picks
                ]
                await self._session.execute(insert(PickModel).values(pick_values))

    # ─────────────────────────── get ───────────────────────────

    async def get(self, backtest_id: BacktestId) -> Backtest | None:
        root = (
            await self._session.execute(
                select(BacktestModel).where(BacktestModel.id == backtest_id)
            )
        ).scalar_one_or_none()
        if root is None:
            return None

        params = self._rebuild_parameters(root)
        error = self._rebuild_error(root.error_detail)
        result = await self._load_result(backtest_id)
        snapshot = await self._load_snapshot(backtest_id)

        return Backtest.rehydrate(
            id=root.id,
            name=root.name,
            created_by=root.created_by,
            parameters=params,
            created_at=root.created_at,
            status=BacktestStatus(root.status),
            started_at=root.started_at,
            completed_at=root.completed_at,
            weeks_total=root.weeks_total,
            weeks_processed=root.weeks_processed,
            error=error,
            result=result,
            snapshot=snapshot,
        )

    @staticmethod
    def _rebuild_parameters(root: BacktestModel) -> BacktestParameters:
        # Postgres normaliza DATERANGE a `[lower, upper+1day)`.
        period = root.period
        start_date = period.lower
        end_date = period.upper - timedelta(days=1)
        return BacktestParameters(
            period_start=Week(start_date),
            period_end=Week(end_date),
            initial_capital=Money(root.initial_capital, root.base_currency),
            strategy_code=root.strategy_code,
            benchmark_code=root.benchmark_code,
        )

    @staticmethod
    def _rebuild_error(detail: dict | None) -> BacktestError | None:
        if detail is None:
            return None
        return BacktestError(
            code=detail.get("code", "unknown"),
            message=detail.get("message", ""),
            context=detail.get("context"),
        )

    async def _load_result(self, backtest_id: BacktestId) -> BacktestResult | None:
        row = (
            await self._session.execute(
                select(ResultModel).where(ResultModel.backtest_id == backtest_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        pts = (
            (
                await self._session.execute(
                    select(EquityPointModel)
                    .where(EquityPointModel.backtest_id == backtest_id)
                    .order_by(EquityPointModel.series, EquityPointModel.point_date)
                )
            )
            .scalars()
            .all()
        )
        equity_curve = tuple(
            EquityPoint(
                series=EquitySeries(pt.series),
                point_date=pt.point_date,
                value=pt.value,
            )
            for pt in pts
        )
        return BacktestResult(
            total_return=row.total_return,
            cagr=row.cagr,
            volatility=row.volatility,
            sharpe=row.sharpe,
            max_drawdown=row.max_drawdown,
            equity_curve=equity_curve,
            metrics_extra=row.metrics_extra,
        )

    async def _load_snapshot(self, backtest_id: BacktestId) -> ReproducibilitySnapshot | None:
        weeks = (
            (
                await self._session.execute(
                    select(WeekModel)
                    .where(WeekModel.backtest_id == backtest_id)
                    .order_by(WeekModel.week_date)
                )
            )
            .scalars()
            .all()
        )
        if not weeks:
            return None
        snapshot_weeks: list[SnapshotWeek] = []
        for w in weeks:
            picks = (
                (
                    await self._session.execute(
                        select(PickModel)
                        .where(PickModel.snapshot_week_id == w.id)
                        .order_by(PickModel.ticker)
                    )
                )
                .scalars()
                .all()
            )
            sp_picks = tuple(
                SnapshotPick(
                    ticker=TickerSymbol(p.ticker),
                    ohlc=OHLC(
                        open=p.open,
                        high=p.high,
                        low=p.low,
                        close=p.close,
                        currency="USD",  # divisa base del backtest, no se persiste por pick
                    ),
                    fx_pair=p.fx_pair,
                    fx_rate=p.fx_rate,
                )
                for p in picks
            )
            snapshot_weeks.append(
                SnapshotWeek(
                    week=Week(w.week_date),
                    resolved_run_id=w.resolved_run_id,
                    run_code=w.run_code,
                    picks=sp_picks,
                )
            )
        return ReproducibilitySnapshot(weeks=tuple(snapshot_weeks))
