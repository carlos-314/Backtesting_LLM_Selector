"""Tests de los VOs de snapshot y resultado (F2 §5.2, §5.3, §8.1)."""
from datetime import date
from decimal import Decimal

import pytest

from app.domain.backtesting.result import BacktestResult, EquityPoint, EquitySeries
from app.domain.backtesting.snapshot import (
    OHLC,
    ReproducibilitySnapshot,
    SnapshotPick,
    SnapshotWeek,
)
from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week


def _ohlc(o="100", h="105", l="98", c="103", cur="USD") -> OHLC:
    return OHLC(Decimal(o), Decimal(h), Decimal(l), Decimal(c), cur)


# ═══════════════════════════════ OHLC ═══════════════════════════════


def test_ohlc_construye_con_decimales_validos() -> None:
    o = _ohlc()
    assert o.open == Decimal("100")
    assert o.close == Decimal("103")


def test_ohlc_low_mayor_que_high_lanza_error() -> None:
    with pytest.raises(ValueError, match="low<=open<=high"):
        OHLC(Decimal("100"), Decimal("50"), Decimal("60"), Decimal("70"), "USD")


def test_ohlc_close_fuera_de_low_high_lanza_error() -> None:
    with pytest.raises(ValueError, match="low<=close<=high"):
        OHLC(Decimal("100"), Decimal("105"), Decimal("98"), Decimal("110"), "USD")


def test_ohlc_precio_negativo_lanza_error() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        OHLC(Decimal("-1"), Decimal("105"), Decimal("98"), Decimal("103"), "USD")


def test_ohlc_currency_invalida_lanza_error() -> None:
    with pytest.raises(ValueError, match="ISO-4217"):
        _ohlc(cur="usd")


def test_ohlc_no_decimal_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        OHLC(100.5, Decimal("105"), Decimal("98"), Decimal("103"), "USD")  # type: ignore[arg-type]


# ═══════════════════════════ SnapshotPick ═══════════════════════════


def test_snapshot_pick_sin_fx_es_valido() -> None:
    p = SnapshotPick(ticker=TickerSymbol("AAPL"), ohlc=_ohlc())
    assert p.fx_pair is None and p.fx_rate is None


def test_snapshot_pick_con_fx_completo_es_valido() -> None:
    p = SnapshotPick(
        ticker=TickerSymbol("TSE.TO"),
        ohlc=_ohlc(cur="CAD"),
        fx_pair="CAD/USD",
        fx_rate=Decimal("0.74"),
    )
    assert p.fx_pair == "CAD/USD"


def test_snapshot_pick_fx_pair_sin_rate_lanza_error() -> None:
    with pytest.raises(ValueError, match="both None or both present"):
        SnapshotPick(
            ticker=TickerSymbol("AAPL"),
            ohlc=_ohlc(),
            fx_pair="CAD/USD",
            fx_rate=None,
        )


def test_snapshot_pick_fx_rate_negativo_lanza_error() -> None:
    with pytest.raises(ValueError, match="positive"):
        SnapshotPick(
            ticker=TickerSymbol("AAPL"),
            ohlc=_ohlc(cur="CAD"),
            fx_pair="CAD/USD",
            fx_rate=Decimal("-1"),
        )


# ═══════════════════════════ SnapshotWeek ═══════════════════════════


def test_snapshot_week_con_picks_unicos_construye() -> None:
    w = SnapshotWeek(
        week=Week(date(2026, 1, 5)),
        resolved_run_id=42,
        run_code="RUN_X",
        picks=(
            SnapshotPick(TickerSymbol("AAPL"), _ohlc()),
            SnapshotPick(TickerSymbol("MSFT"), _ohlc()),
        ),
    )
    assert len(w.picks) == 2


def test_snapshot_week_con_tickers_duplicados_lanza_error() -> None:
    with pytest.raises(ValueError, match="Duplicated ticker"):
        SnapshotWeek(
            week=Week(date(2026, 1, 5)),
            resolved_run_id=42,
            run_code="RUN_X",
            picks=(
                SnapshotPick(TickerSymbol("AAPL"), _ohlc()),
                SnapshotPick(TickerSymbol("AAPL"), _ohlc(c="105")),
            ),
        )


def test_snapshot_week_picks_no_tupla_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="tuple"):
        SnapshotWeek(
            week=Week(date(2026, 1, 5)),
            resolved_run_id=42,
            run_code="RUN_X",
            picks=[SnapshotPick(TickerSymbol("AAPL"), _ohlc())],  # type: ignore[arg-type]
        )


def test_snapshot_week_picks_vacios_se_permite_aqui() -> None:
    """ADR-0004 ya filtra ≥1 pick en el WeekResolver; el VO solo persiste."""
    w = SnapshotWeek(
        week=Week(date(2026, 1, 5)), resolved_run_id=42, run_code=None, picks=()
    )
    assert w.picks == ()


# ═════════════════════ ReproducibilitySnapshot ═════════════════════


def test_snapshot_orden_temporal_creciente_es_valido() -> None:
    s = ReproducibilitySnapshot(
        weeks=(
            SnapshotWeek(Week(date(2026, 1, 5)), 1, None, ()),
            SnapshotWeek(Week(date(2026, 1, 12)), 2, None, ()),
            SnapshotWeek(Week(date(2026, 1, 26)), 3, None, ()),  # gap permitido
        )
    )
    assert len(s.weeks) == 3


def test_snapshot_orden_temporal_descendente_lanza_error() -> None:
    with pytest.raises(ValueError, match="chronological order"):
        ReproducibilitySnapshot(
            weeks=(
                SnapshotWeek(Week(date(2026, 1, 12)), 2, None, ()),
                SnapshotWeek(Week(date(2026, 1, 5)), 1, None, ()),
            )
        )


def test_snapshot_semanas_duplicadas_lanzan_error() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ReproducibilitySnapshot(
            weeks=(
                SnapshotWeek(Week(date(2026, 1, 5)), 1, None, ()),
                SnapshotWeek(Week(date(2026, 1, 5)), 99, None, ()),
            )
        )


def test_snapshot_vacio_es_valido() -> None:
    """Backtest sin ninguna semana resuelta (edge): el VO no decide; el
    `BacktestEngine` puede decidir fallar antes de llegar aquí."""
    assert ReproducibilitySnapshot(weeks=()).weeks == ()


# ═════════════════════════ EquityPoint / BacktestResult ═════════════════════════


def test_equity_point_value_no_decimal_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        EquityPoint(series=EquitySeries.PORTFOLIO, point_date=date(2026, 1, 5), value=100)  # type: ignore[arg-type]


def test_result_vacio_es_valido() -> None:
    r = BacktestResult()
    assert r.total_return is None
    assert r.equity_curve == ()


def test_result_equity_curve_ordenada_por_serie_es_valida() -> None:
    pts = (
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 5), Decimal("100")),
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 12), Decimal("103")),
        EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 5), Decimal("100")),
        EquityPoint(EquitySeries.BENCHMARK, date(2026, 1, 12), Decimal("101")),
    )
    r = BacktestResult(total_return=Decimal("0.03"), equity_curve=pts)
    assert len(r.equity_curve) == 4


def test_result_equity_curve_desordenada_dentro_de_serie_lanza_error() -> None:
    pts = (
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 12), Decimal("103")),
        EquityPoint(EquitySeries.PORTFOLIO, date(2026, 1, 5), Decimal("100")),
    )
    with pytest.raises(ValueError, match="chronological"):
        BacktestResult(equity_curve=pts)


def test_result_equity_curve_no_tupla_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="tuple"):
        BacktestResult(equity_curve=[])  # type: ignore[arg-type]
