"""Read models planos del contexto Análisis (F2 §4.6).

No son entidades DDD: no tienen invariantes que proteger ni comportamiento;
son la cara limpia con la que el dominio lee la BBDD de análisis a través de
la ACL. Los produce la ACL ya traducidos del esquema sucio externo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.shared.ticker import TickerSymbol


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    """Un run del pipeline externo (proviene de `analysis_runs` en Railway).

    `status` es el VALOR CRUDO del campo externo. El criterio "es OK" vive
    en `WeekResolver.is_ok(...)` (ADR-0004), no aquí.

    `pick_count` lo precomputa la ACL (`COUNT(*) FROM portfolios WHERE id_run=...`).
    El resolver no consulta picks por su cuenta para mantener su pureza.
    """

    id: int  # id_run externo (INTEGER en la legacy)
    fecha_run: datetime  # timezone-aware (ACL lo convierte al leer)
    run_code: str
    status: str
    pick_count: int

    def __post_init__(self) -> None:
        if self.fecha_run.tzinfo is None:
            raise ValueError(
                f"AnalysisRun.fecha_run must be timezone-aware; got naive for id_run={self.id}"
            )
        if self.pick_count < 0:
            raise ValueError(
                f"AnalysisRun.pick_count must be >= 0; got {self.pick_count} for id_run={self.id}"
            )


@dataclass(frozen=True, slots=True)
class Pick:
    """Un pick del run (fila de `portfolios` en Railway)."""

    ticker: TickerSymbol
    role: str | None  # `portfolios.rol`
    nombre: str | None
