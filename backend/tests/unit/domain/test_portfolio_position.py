"""Tests unitarios de `PortfolioPosition` (F2 §4.6, §8.1)."""
from decimal import Decimal

import pytest

from app.domain.backtesting.portfolio_position import PortfolioPosition
from app.domain.shared.money import CurrencyMismatchError, Money
from app.domain.shared.ticker import TickerSymbol


def _pos(shares: str = "10", price: str = "100") -> PortfolioPosition:
    return PortfolioPosition(
        ticker=TickerSymbol("AAPL"),
        shares=Decimal(shares),
        entry_price=Money.usd(price),
    )


# ─────────────────────── Validación ───────────────────────


def test_position_construye_con_shares_positivas() -> None:
    p = _pos("10", "150")
    assert p.shares == Decimal("10")
    assert p.entry_price == Money.usd("150")


def test_position_shares_cero_lanza_error() -> None:
    with pytest.raises(ValueError, match="positive"):
        PortfolioPosition(
            ticker=TickerSymbol("AAPL"),
            shares=Decimal("0"),
            entry_price=Money.usd("100"),
        )


def test_position_shares_negativas_lanza_error() -> None:
    with pytest.raises(ValueError, match="positive"):
        PortfolioPosition(
            ticker=TickerSymbol("AAPL"),
            shares=Decimal("-5"),
            entry_price=Money.usd("100"),
        )


def test_position_shares_no_decimal_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        PortfolioPosition(
            ticker=TickerSymbol("AAPL"),
            shares=10,  # type: ignore[arg-type]
            entry_price=Money.usd("100"),
        )


# ─────────────────────── cost_basis ───────────────────────


def test_position_cost_basis_es_shares_por_entry_price() -> None:
    p = _pos("10", "150")
    assert p.cost_basis() == Money.usd("1500")


def test_position_cost_basis_con_shares_fraccionarias() -> None:
    p = PortfolioPosition(
        ticker=TickerSymbol("AAPL"),
        shares=Decimal("2.5"),
        entry_price=Money.usd("100"),
    )
    assert p.cost_basis() == Money.usd("250.0")


def test_position_cost_basis_conserva_divisa_de_entrada() -> None:
    p = PortfolioPosition(
        ticker=TickerSymbol("MERV-A"),
        shares=Decimal("10"),
        entry_price=Money(Decimal("100"), "ARS"),
    )
    assert p.cost_basis() == Money(Decimal("1000"), "ARS")


# ─────────────────────── value_at ───────────────────────


def test_position_value_at_misma_divisa_devuelve_money() -> None:
    p = _pos("10", "150")
    assert p.value_at(Money.usd("180")) == Money.usd("1800")


def test_position_value_at_distinta_divisa_lanza_error() -> None:
    """El VO no convierte divisas; eso es responsabilidad del puerto FX."""
    p = _pos("10", "150")
    with pytest.raises(CurrencyMismatchError):
        p.value_at(Money(Decimal("180"), "EUR"))


def test_position_value_at_precio_caido_a_la_mitad() -> None:
    p = _pos("10", "100")
    assert p.value_at(Money.usd("50")) == Money.usd("500")


# ─────────────────────── Inmutabilidad ───────────────────────


def test_position_es_inmutable() -> None:
    p = _pos()
    with pytest.raises(Exception):
        p.shares = Decimal("999")  # type: ignore[misc]


def test_position_mismas_props_es_igual_y_hashable() -> None:
    a = _pos("10", "150")
    b = PortfolioPosition(
        ticker=TickerSymbol("AAPL"),
        shares=Decimal("10"),
        entry_price=Money.usd("150"),
    )
    assert a == b
    assert hash(a) == hash(b)
