"""Value Object `Week` (F2 §4.3).

Definición cerrada de "semana" para todo el dominio:

- **Zona horaria de referencia:** `America/New_York`. El mercado es USA/NASDAQ;
  alinear con su sesión bursátil evita que un run nocturno europeo caiga en la
  "semana equivocada".
- **Inicio de semana:** lunes 00:00 NY.
- **Intervalo:** `[lunes 00:00, lunes siguiente 00:00)` (semiabierto).
- **`week_date` canónica:** la fecha del lunes de esa semana (en NY).

Esta clase es Value Object: inmutable, igualdad por valor, sin identidad.
La reproducibilidad del snapshot del backtest depende de esta convención.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class Week:
    """`week_date` es el lunes canónico (fecha de calendario en NY)."""

    week_date: date

    def __post_init__(self) -> None:
        if self.week_date.weekday() != 0:
            raise ValueError(
                f"Week.week_date must be a Monday; got {self.week_date} "
                f"({self.week_date.strftime('%A')})"
            )

    # ───────────────────────── constructores ─────────────────────────

    @classmethod
    def from_instant(cls, instant: datetime) -> Week:
        """Asigna un instante temporal a la semana que lo contiene.

        El instante DEBE ser timezone-aware: un naive datetime no permite
        determinar a qué semana NY pertenece (F1 §7.3 / F2 §3 — fallar claro).
        """
        if instant.tzinfo is None:
            raise ValueError(
                "Week.from_instant requires a timezone-aware datetime; got naive"
            )
        ny = instant.astimezone(NEW_YORK)
        monday_ny = (ny - timedelta(days=ny.weekday())).date()
        return cls(week_date=monday_ny)

    @classmethod
    def from_iso(cls, iso_date: str) -> Week:
        """Construye desde `YYYY-MM-DD` (debe ser un lunes NY)."""
        return cls(week_date=date.fromisoformat(iso_date))

    # ──────────────────────── propiedades temporales ────────────────────────

    @property
    def start_ny(self) -> datetime:
        """Instante de inicio (lunes 00:00 NY)."""
        return datetime.combine(self.week_date, time(0, 0), tzinfo=NEW_YORK)

    @property
    def end_ny(self) -> datetime:
        """Instante de fin EXCLUSIVO (lunes siguiente 00:00 NY)."""
        return self.next().start_ny

    # ─────────────────────────── operaciones ───────────────────────────

    def contains(self, instant: datetime) -> bool:
        """¿El instante cae en `[start_ny, end_ny)`?"""
        if instant.tzinfo is None:
            raise ValueError(
                "Week.contains requires a timezone-aware datetime; got naive"
            )
        ny = instant.astimezone(NEW_YORK)
        return self.start_ny <= ny < self.end_ny

    def next(self) -> Week:
        return Week(week_date=self.week_date + timedelta(days=7))

    def previous(self) -> Week:
        return Week(week_date=self.week_date - timedelta(days=7))

    def __str__(self) -> str:
        return self.week_date.isoformat()
