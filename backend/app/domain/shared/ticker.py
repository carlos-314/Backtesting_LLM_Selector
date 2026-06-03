"""Value Object `TickerSymbol` (F2 §4.6).

Símbolo de bolsa normalizado (uppercase). Permite letras, números, `.` y `-`
para cubrir tickers reales como `BRK.B` (Berkshire B) o `MERV-A`.
"""
from __future__ import annotations

from dataclasses import dataclass

_ALLOWED_EXTRA = set(".-")
_MAX_LEN = 20


@dataclass(frozen=True, slots=True)
class TickerSymbol:
    value: str

    def __post_init__(self) -> None:
        v = self.value
        if not v:
            raise ValueError("TickerSymbol cannot be empty")
        if len(v) > _MAX_LEN:
            raise ValueError(f"TickerSymbol too long (>{_MAX_LEN}): {v!r}")
        if v != v.upper():
            raise ValueError(
                f"TickerSymbol must be uppercase; got {v!r} — use TickerSymbol.of() to normalize"
            )
        for ch in v:
            if not (ch.isalnum() or ch in _ALLOWED_EXTRA):
                raise ValueError(f"TickerSymbol has invalid character {ch!r}: {v!r}")
        if v[0] in _ALLOWED_EXTRA or v[-1] in _ALLOWED_EXTRA:
            raise ValueError(
                f"TickerSymbol cannot start or end with '.' or '-': {v!r}"
            )

    @classmethod
    def of(cls, text: str) -> TickerSymbol:
        """Constructor con normalización (trim + uppercase)."""
        return cls(value=text.strip().upper())

    def __str__(self) -> str:
        return self.value
