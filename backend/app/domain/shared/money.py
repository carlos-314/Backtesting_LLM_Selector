"""Value Object `Money` (F2 §4.6).

Importe + divisa, inmutable. Las aritméticas exigen misma divisa; cruzar
divisas requiere `PriceProviderPort` (no es responsabilidad de este VO).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class CurrencyMismatchError(ValueError):
    """Operación aritmética con divisas distintas."""


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str  # ISO-4217 (3 letras, mayúsculas)

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"Money.amount must be Decimal; got {type(self.amount).__name__}"
            )
        if not (
            isinstance(self.currency, str)
            and len(self.currency) == 3
            and self.currency.isalpha()
            and self.currency.isupper()
        ):
            raise ValueError(
                f"Money.currency must be ISO-4217 (3 uppercase letters); got {self.currency!r}"
            )

    # ───────────────────────────── aritmética ─────────────────────────────

    def _check_same_currency(self, other: Money) -> None:
        if other.currency != self.currency:
            raise CurrencyMismatchError(
                f"Cannot operate on Money of {self.currency} and {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self._check_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, scalar: Decimal | int) -> Money:
        if isinstance(scalar, float):
            raise TypeError(
                "Multiplying Money by float is forbidden; use Decimal to avoid precision loss"
            )
        return Money(self.amount * Decimal(scalar), self.currency)

    __rmul__ = __mul__

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    # ──────────────────────────── comparaciones ────────────────────────────

    def __lt__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self.amount >= other.amount

    # ────────────────────────────── factory ──────────────────────────────

    @classmethod
    def usd(cls, amount: Decimal | int | str) -> Money:
        """Conveniencia: día uno reporte en USD (F0/F1)."""
        return cls(Decimal(amount), "USD")

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
