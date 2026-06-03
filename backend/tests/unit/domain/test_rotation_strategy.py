"""Tests de la estrategia día uno `WeeklyRotationStrategy` (F2 §4.7, §8.1)."""
from decimal import Decimal

import pytest

from app.domain.backtesting.portfolio_position import PortfolioPosition
from app.domain.backtesting.snapshot import OHLC
from app.domain.backtesting.strategy import (
    RotationStrategy,
    WeeklyRotationStrategy,
)
from app.domain.shared.money import Money
from app.domain.shared.ticker import TickerSymbol


def _ohlc(o="100", h=None, l=None, c="103", cur="USD") -> OHLC:
    """Helper que mantiene la invariante OHLC sin requerir pasar h/l a mano.

    Si `h`/`l` no se pasan, se derivan de los extremos de open/close.
    """
    open_d = Decimal(o)
    close_d = Decimal(c)
    high_d = Decimal(h) if h is not None else max(open_d, close_d)
    low_d = Decimal(l) if l is not None else min(open_d, close_d)
    return OHLC(open_d, high_d, low_d, close_d, cur)


def _pos(ticker: str, shares: str, entry: str) -> PortfolioPosition:
    return PortfolioPosition(
        ticker=TickerSymbol(ticker),
        shares=Decimal(shares),
        entry_price=Money.usd(entry),
    )


@pytest.fixture
def strategy() -> WeeklyRotationStrategy:
    return WeeklyRotationStrategy()


# ─────────────── Interfaz / contrato ───────────────


def test_weekly_rotation_implementa_protocolo_RotationStrategy() -> None:
    assert isinstance(WeeklyRotationStrategy(), RotationStrategy)


def test_weekly_rotation_code_es_weekly_rotation() -> None:
    assert WeeklyRotationStrategy.code == "weekly_rotation"


# ─────────────── Primer rebalanceo: cash → posiciones ───────────────


def test_primer_rebalanceo_compra_target_a_close_con_1_N_del_cash(
    strategy: WeeklyRotationStrategy,
) -> None:
    cash = Money.usd("10000")
    target = frozenset({TickerSymbol("AAPL"), TickerSymbol("MSFT")})
    ohlc = {
        TickerSymbol("AAPL"): _ohlc(o="100", c="100"),
        TickerSymbol("MSFT"): _ohlc(o="200", c="200"),
    }
    result = strategy.rotate(
        current_positions=(),
        target_tickers=target,
        ohlc=ohlc,
        cash=cash,
    )
    assert len(result.positions) == 2
    # 10000 / 2 = 5000 cada uno
    aapl = next(p for p in result.positions if str(p.ticker) == "AAPL")
    msft = next(p for p in result.positions if str(p.ticker) == "MSFT")
    assert aapl.shares == Decimal("50")  # 5000 / 100
    assert msft.shares == Decimal("25")  # 5000 / 200
    assert aapl.entry_price == Money.usd("100")
    assert msft.entry_price == Money.usd("200")


def test_target_vacio_y_cash_solo_no_compra_nada(
    strategy: WeeklyRotationStrategy,
) -> None:
    cash = Money.usd("10000")
    result = strategy.rotate(
        current_positions=(),
        target_tickers=frozenset(),
        ohlc={},
        cash=cash,
    )
    assert result.positions == ()
    assert result.cash == cash


# ─────────────── Rebalanceo: salientes → open ───────────────


def test_saliente_se_vende_a_OPEN_no_a_close(strategy: WeeklyRotationStrategy) -> None:
    """Caso crítico F2 §4.7: salientes salen al OPEN, no al close."""
    current = (_pos("OLD", "10", "100"),)  # entry=100, mantiene 10 acciones
    cash = Money.usd("0")
    ohlc = {
        TickerSymbol("OLD"): _ohlc(o="120", c="150"),  # open=120, close=150
    }
    result = strategy.rotate(
        current_positions=current,
        target_tickers=frozenset(),
        ohlc=ohlc,
        cash=cash,
    )
    # Vende 10 * open(120) = 1200. NO 10 * close(150) = 1500.
    assert result.cash == Money.usd("1200")
    assert result.positions == ()


def test_saliente_en_otra_divisa_no_se_mezcla_con_cash_USD(
    strategy: WeeklyRotationStrategy,
) -> None:
    """Sanity: si la divisa del precio no coincide con cash, falla limpio
    (Money lo detecta). En el flujo real, el adaptador FX convertiría antes."""
    current = (
        PortfolioPosition(
            ticker=TickerSymbol("TSE"),
            shares=Decimal("10"),
            entry_price=Money(Decimal("100"), "CAD"),
        ),
    )
    cash = Money.usd("0")
    ohlc = {TickerSymbol("TSE"): _ohlc(o="120", c="130", cur="CAD")}
    with pytest.raises(Exception):
        strategy.rotate(
            current_positions=current,
            target_tickers=frozenset(),
            ohlc=ohlc,
            cash=cash,
        )


# ─────────────── Rebalanceo: entrantes → close ───────────────


def test_entrante_se_compra_a_CLOSE_no_a_open(strategy: WeeklyRotationStrategy) -> None:
    cash = Money.usd("1000")
    ohlc = {TickerSymbol("NEW"): _ohlc(o="80", c="100")}
    result = strategy.rotate(
        current_positions=(),
        target_tickers=frozenset({TickerSymbol("NEW")}),
        ohlc=ohlc,
        cash=cash,
    )
    # 1000 / 100 = 10 acciones (compra al CLOSE=100, no al OPEN=80)
    assert result.positions[0].shares == Decimal("10")
    assert result.positions[0].entry_price == Money.usd("100")


# ─────────────── Rebalanceo: salida + entrada en la misma rotación ───────────────


def test_rotacion_mixta_vende_a_open_y_compra_a_close(
    strategy: WeeklyRotationStrategy,
) -> None:
    """Caso típico: AAPL fuera, MSFT dentro."""
    current = (_pos("AAPL", "10", "150"),)
    cash = Money.usd("500")
    target = frozenset({TickerSymbol("MSFT")})
    ohlc = {
        TickerSymbol("AAPL"): _ohlc(o="180", c="185"),  # se vende a 180
        TickerSymbol("MSFT"): _ohlc(o="50", c="60"),  # se compra a 60
    }
    result = strategy.rotate(
        current_positions=current,
        target_tickers=target,
        ohlc=ohlc,
        cash=cash,
    )
    # Cash tras vender AAPL: 500 + 10*180 = 2300
    # Comprar MSFT: 2300 / 60 ≈ 38.333333
    msft = result.positions[0]
    assert msft.ticker == TickerSymbol("MSFT")
    assert msft.entry_price == Money.usd("60")
    assert msft.shares == Decimal("38.333333")


# ─────────────── Mantenidas: no se tocan ───────────────


def test_mantenida_no_se_toca_aunque_precio_cambie(
    strategy: WeeklyRotationStrategy,
) -> None:
    """Decisión consciente F2 §4.7: las que se mantienen no se rebalancean."""
    current = (_pos("AAPL", "10", "100"),)  # ya en cartera
    cash = Money.usd("0")
    target = frozenset({TickerSymbol("AAPL")})  # sigue siendo target
    ohlc = {TickerSymbol("AAPL"): _ohlc(o="200", c="250")}
    result = strategy.rotate(
        current_positions=current,
        target_tickers=target,
        ohlc=ohlc,
        cash=cash,
    )
    assert len(result.positions) == 1
    p = result.positions[0]
    assert p.shares == Decimal("10")  # SIN cambio
    assert p.entry_price == Money.usd("100")  # entry SIN cambio
    assert result.cash == Money.usd("0")


# ─────────────── Edge cases ───────────────


def test_ohlc_falta_para_un_ticker_target_lanza_keyerror(
    strategy: WeeklyRotationStrategy,
) -> None:
    """El engine debió calentar la caché antes; si falta, falla claro."""
    with pytest.raises(KeyError, match="Missing OHLC"):
        strategy.rotate(
            current_positions=(),
            target_tickers=frozenset({TickerSymbol("X")}),
            ohlc={},
            cash=Money.usd("100"),
        )


def test_close_cero_para_entrante_lanza_error(strategy: WeeklyRotationStrategy) -> None:
    with pytest.raises(ValueError, match="close=0"):
        strategy.rotate(
            current_positions=(),
            target_tickers=frozenset({TickerSymbol("X")}),
            ohlc={TickerSymbol("X"): _ohlc(c="0", l="0")},
            cash=Money.usd("100"),
        )


def test_budget_demasiado_pequeno_para_un_ticker_lo_salta(
    strategy: WeeklyRotationStrategy,
) -> None:
    """Con cash tan pequeño que budget/close < 1e-6, se salta esa posición.
    No es error: la estrategia procede con el resto."""
    cash = Money.usd("0.000001")
    target = frozenset({TickerSymbol("EXPENSIVE")})
    ohlc = {TickerSymbol("EXPENSIVE"): _ohlc(c="10000000")}
    result = strategy.rotate(
        current_positions=(),
        target_tickers=target,
        ohlc=ohlc,
        cash=cash,
    )
    # Budget / close ≈ 1e-13, redondeado a 6 decimales = 0 → se salta
    assert result.positions == ()


def test_orden_de_compra_es_alfabetico_por_ticker(
    strategy: WeeklyRotationStrategy,
) -> None:
    """Determinismo del resultado (importante para tests y reproducibilidad)."""
    cash = Money.usd("3000")
    target = frozenset({TickerSymbol("ZZ"), TickerSymbol("AA"), TickerSymbol("MM")})
    ohlc = {
        TickerSymbol("ZZ"): _ohlc(c="10"),
        TickerSymbol("AA"): _ohlc(c="10"),
        TickerSymbol("MM"): _ohlc(c="10"),
    }
    result = strategy.rotate(
        current_positions=(),
        target_tickers=target,
        ohlc=ohlc,
        cash=cash,
    )
    tickers = [str(p.ticker) for p in result.positions]
    assert tickers == ["AA", "MM", "ZZ"]
