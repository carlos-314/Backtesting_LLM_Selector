"""Servicio de dominio `WeekResolver` (F2 §4.7, ADR-0004).

Agrupa runs por semana (definición de `Week`, F2 §4.3) y, dentro de cada
semana, resuelve "último run OK gana". Si ningún run de la semana es OK, la
semana se descarta (no se muestra ni entra en backtests).

Regla "OK" (ADR-0004): `status = 'COMPLETED'` Y `pick_count > 0`.

El servicio es puro: no toca BBDD ni red. Loguea estructuradamente cada run
descartado con su `reason`, lo que permite diagnóstico operativo (F2 §7.1).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Final

from app.domain.screening.read_models import AnalysisRun
from app.domain.shared.week import Week

log = logging.getLogger(__name__)

OK_STATUS: Final[str] = "COMPLETED"

# Razones de descarte, vocabulario cerrado para logs y futuros consumidores.
REASON_STATUS_NOT_COMPLETED: Final[str] = "status_not_completed"
REASON_NO_PICKS: Final[str] = "no_picks"
REASON_STATUS_UNKNOWN_FAILSAFE: Final[str] = "status_unknown_failsafe"

# Valores conocidos del campo `status` (ADR-0004 verificó el dominio real).
# Si la ACL encuentra otro, el WeekResolver aplica fail-safe y loguea.
KNOWN_STATUSES: Final[frozenset[str]] = frozenset({"COMPLETED", "STARTED"})


class WeekResolver:
    """Servicio puro. Sin estado; métodos estáticos."""

    @staticmethod
    def is_ok(run: AnalysisRun) -> bool:
        """Implementa la regla cerrada de ADR-0004."""
        return run.status == OK_STATUS and run.pick_count > 0

    @staticmethod
    def _classify_not_ok(run: AnalysisRun) -> str:
        """Devuelve el `reason` por el que un run NO es OK."""
        if run.status not in KNOWN_STATUSES:
            return REASON_STATUS_UNKNOWN_FAILSAFE
        if run.status != OK_STATUS:
            return REASON_STATUS_NOT_COMPLETED
        # status == 'COMPLETED' pero pick_count == 0
        return REASON_NO_PICKS

    @classmethod
    def resolve_weeks(cls, runs: Iterable[AnalysisRun]) -> dict[Week, AnalysisRun]:
        """Agrupa los runs por semana (NY) y, dentro de cada semana, devuelve
        el más reciente que sea OK. Semanas sin ningún OK no aparecen.

        Args:
            runs: iterable de read-models producidos por la ACL.

        Returns:
            dict {Week → AnalysisRun ganador}. Iteración no determinista en
            cuanto al orden; usa `sorted(result.items(), key=...)` si necesitas
            orden.
        """
        winners: dict[Week, AnalysisRun] = {}

        for run in runs:
            week = Week.from_instant(run.fecha_run)

            if not cls.is_ok(run):
                reason = cls._classify_not_ok(run)
                log.info(
                    "run_not_ok id_run=%s week=%s status=%r picks=%s reason=%s",
                    run.id,
                    week,
                    run.status,
                    run.pick_count,
                    reason,
                    extra={
                        "event": "run_not_ok",
                        "id_run": run.id,
                        "week": str(week),
                        "status": run.status,
                        "pick_count": run.pick_count,
                        "reason": reason,
                    },
                )
                continue

            incumbent = winners.get(week)
            if incumbent is None or run.fecha_run > incumbent.fecha_run:
                winners[week] = run

        return winners
