"""Snapshot de reproducibilidad (F2 §4.6, §5.3, §7.1).

El snapshot es **copia congelada** de todo lo que el backtest usó: semanas →
run resuelto → picks → OHLC y FX usados. NO contiene FK a la BBDD de análisis
(F2 §5.5: "feeds, no FK"); la copia es la reproducibilidad.

Los precios OHLC se guardan en su divisa nativa; `fx_rate` (cuando aplica) es
el tipo de cambio del día de cotización a la divisa base del backtest.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import Week


@dataclass(frozen=True, slots=True)
class OHLC:
    """Open/High/Low/Close de un ticker en una fecha, en su divisa nativa."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    currency: str

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"OHLC.{name} must be Decimal; got {type(v).__name__}")
            if v < 0:
                raise ValueError(f"OHLC.{name} must be non-negative; got {v}")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"OHLC violates low<=open<=high: {self}")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"OHLC violates low<=close<=high: {self}")
        if len(self.currency) != 3 or not self.currency.isupper() or not self.currency.isalpha():
            raise ValueError(f"OHLC.currency must be ISO-4217; got {self.currency!r}")


@dataclass(frozen=True, slots=True)
class SnapshotPick:
    """Pick congelado en el snapshot, con OHLC y FX usados (F2 §5.3)."""

    ticker: TickerSymbol
    ohlc: OHLC
    fx_pair: str | None = None  # None si ya cotiza en la base_currency del backtest
    fx_rate: Decimal | None = None

    def __post_init__(self) -> None:
        # Coherencia: fx_pair y fx_rate son ambos None o ambos presentes.
        if (self.fx_pair is None) != (self.fx_rate is None):
            raise ValueError(
                "SnapshotPick.fx_pair and fx_rate must be both None or both present"
            )
        if self.fx_rate is not None:
            if not isinstance(self.fx_rate, Decimal):
                raise TypeError("fx_rate must be Decimal")
            if self.fx_rate <= 0:
                raise ValueError(f"fx_rate must be positive; got {self.fx_rate}")


@dataclass(frozen=True, slots=True)
class SnapshotWeek:
    """Una semana del snapshot, con su run resuelto y sus picks (F2 §5.3)."""

    week: Week
    resolved_run_id: int  # copia del id externo, sin FK
    run_code: str | None
    picks: tuple[SnapshotPick, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.picks, tuple):
            raise TypeError("SnapshotWeek.picks must be a tuple (immutable)")
        # No exigimos picks > 0 aquí: la regla "≥1 pick" la garantiza ADR-0004
        # en el WeekResolver; aquí solo persistimos lo que ya pasó el filtro.
        seen = set()
        for p in self.picks:
            if p.ticker in seen:
                raise ValueError(f"Duplicated ticker in SnapshotWeek: {p.ticker}")
            seen.add(p.ticker)


@dataclass(frozen=True, slots=True)
class ReproducibilitySnapshot:
    """Snapshot completo: tupla de semanas en orden temporal (F2 §4.6)."""

    weeks: tuple[SnapshotWeek, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.weeks, tuple):
            raise TypeError("ReproducibilitySnapshot.weeks must be a tuple")
        # Orden temporal estricto creciente (sin huecos NO se exige; el resolver
        # ya pudo haber descartado semanas).
        dates = [w.week.week_date for w in self.weeks]
        if dates != sorted(dates):
            raise ValueError("ReproducibilitySnapshot.weeks must be in chronological order")
        if len(set(dates)) != len(dates):
            raise ValueError("ReproducibilitySnapshot.weeks must not have duplicate weeks")
