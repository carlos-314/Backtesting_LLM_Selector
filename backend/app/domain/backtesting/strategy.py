"""Estrategia de rotación (F2 §4.7).

Interfaz `RotationStrategy` + implementación día uno `WeeklyRotationStrategy`:

- **Salientes** (presentes en `current_positions` pero no en `target_tickers`):
  se venden al **open**.
- **Entrantes** (en `target_tickers` pero no en `current_positions`): se compran
  al **close** con equiponderación 1/N del cash disponible tras las ventas.
- **Mantenidas** (en ambos conjuntos): no se tocan (no se rebalancean día uno).
  Decisión consciente: F2 §4.7 dice "entrantes a close / salientes a open" sin
  rebalanceo de las que se mantienen. Esto puede divergir de 1/N puro pero es
  literal a lo descrito.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.domain.backtesting.snapshot import OHLC
from app.domain.backtesting.portfolio_position import PortfolioPosition
from app.domain.shared.money import Money
from app.domain.shared.ticker import TickerSymbol


@dataclass(frozen=True, slots=True)
class RotationResult:
    """Estado de la cartera tras una rotación."""

    positions: tuple[PortfolioPosition, ...]
    cash: Money


@runtime_checkable
class RotationStrategy(Protocol):
    """Contrato de las estrategias de rotación. `code` identifica la estrategia
    en `BacktestParameters.strategy_code` y en `backtest_runs.strategy_code`."""

    code: str

    def rotate(
        self,
        *,
        current_positions: tuple[PortfolioPosition, ...],
        target_tickers: frozenset[TickerSymbol],
        ohlc: dict[TickerSymbol, OHLC],
        cash: Money,
    ) -> RotationResult:
        ...


class WeeklyRotationStrategy:
    """Estrategia día uno: salientes a open, entrantes a close, equiponderación
    1/N entre las entrantes sobre el cash disponible.

    Las posiciones mantenidas (current ∩ target) **no se tocan**. Esto es
    consistente con F2 §4.7 ("entrantes a close / salientes a open").
    """

    code: str = "weekly_rotation"

    def rotate(
        self,
        *,
        current_positions: tuple[PortfolioPosition, ...],
        target_tickers: frozenset[TickerSymbol],
        ohlc: dict[TickerSymbol, OHLC],
        cash: Money,
    ) -> RotationResult:
        # 1) Separar mantenidas y salientes.
        held: list[PortfolioPosition] = []
        exiting: list[PortfolioPosition] = []
        for pos in current_positions:
            if pos.ticker in target_tickers:
                held.append(pos)
            else:
                exiting.append(pos)

        currency = cash.currency

        # 2) Vender salientes al OPEN del día → engrosar el cash.
        new_cash = cash
        for pos in exiting:
            o = self._require_ohlc(ohlc, pos.ticker, "exiting")
            sell_price = Money(o.open, o.currency)
            proceeds = pos.value_at(sell_price)
            new_cash = new_cash + proceeds  # mismas divisas: Money.__add__ valida

        # 3) Entrantes = target \ held.
        held_tickers = {p.ticker for p in held}
        entering = sorted(target_tickers - held_tickers, key=lambda t: t.value)

        # 4) Comprar entrantes al CLOSE con cash/N entre todas las entrantes.
        if entering:
            per_ticker_budget_amount = (new_cash.amount / Decimal(len(entering))).quantize(
                Decimal("0.01")
            )
            per_ticker_budget = Money(per_ticker_budget_amount, currency)
            for tk in entering:
                o = self._require_ohlc(ohlc, tk, "entering")
                buy_price = Money(o.close, o.currency)
                # shares = budget / price (fraccionarias permitidas, F2 no exige enteras)
                if buy_price.amount <= 0:
                    raise ValueError(
                        f"Cannot buy {tk} at close=0 on rotation"
                    )
                shares = (per_ticker_budget.amount / buy_price.amount).quantize(
                    Decimal("0.000001")
                )
                if shares <= 0:
                    # Budget tan pequeño que no podemos comprar ni 1e-6 → saltar.
                    continue
                position = PortfolioPosition(
                    ticker=tk,
                    shares=shares,
                    entry_price=buy_price,
                )
                held.append(position)
                spent = buy_price * shares
                new_cash = new_cash - spent

        return RotationResult(positions=tuple(held), cash=new_cash)

    @staticmethod
    def _require_ohlc(
        ohlc: dict[TickerSymbol, OHLC], ticker: TickerSymbol, role: str
    ) -> OHLC:
        if ticker not in ohlc:
            raise KeyError(
                f"Missing OHLC for {ticker} ({role}); the engine should have warmed up the cache"
            )
        return ohlc[ticker]
