"""Value Object `PortfolioPosition` (F2 §4.6).

Posición individual dentro de una cartera. Sin identidad, sin estado mutable.
El peso de la posición en el portafolio total NO vive aquí (depende del total,
es responsabilidad del agregado `Backtest` o del engine).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.shared.money import CurrencyMismatchError, Money
from app.domain.shared.ticker import TickerSymbol


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    ticker: TickerSymbol
    shares: Decimal
    entry_price: Money

    def __post_init__(self) -> None:
        if not isinstance(self.shares, Decimal):
            raise TypeError(
                f"shares must be Decimal; got {type(self.shares).__name__}"
            )
        if self.shares <= 0:
            raise ValueError(f"shares must be positive; got {self.shares}")

    def cost_basis(self) -> Money:
        """Coste total de entrada de la posición."""
        return self.entry_price * self.shares

    def value_at(self, price: Money) -> Money:
        """Valuación mark-to-market a un precio dado, en su misma divisa."""
        if price.currency != self.entry_price.currency:
            raise CurrencyMismatchError(
                f"Cannot value position in {self.entry_price.currency} "
                f"using price in {price.currency}"
            )
        return price * self.shares
