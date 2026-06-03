"""Agregado raíz `Backtest` (F2 §4.6, §5.2).

Protege la **reproducibilidad** como invariante: solo se marca COMPLETED
cuando snapshot y resultado están dentro, coherentes, en la misma operación.

El agregado es **mutable** (cambia de estado). Las transiciones son métodos
que validan el estado actual antes de cambiarlo. Cualquier intento de
transición ilegal lanza `InvalidStateTransition`.

Diagrama:
    PENDING ──start──▶ RUNNING ──complete──▶ COMPLETED  (terminal)
            └─cancel──────┴─cancel──────────▶ CANCELLED (terminal)
                          └─fail────────────▶ FAILED    (terminal)

Una vez en terminal, ninguna transición más es legal.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.backtesting.parameters import BacktestId, BacktestParameters, BacktestStatus
from app.domain.backtesting.result import BacktestResult
from app.domain.backtesting.snapshot import ReproducibilitySnapshot


class InvalidStateTransition(Exception):
    """Intento de transición ilegal sobre el agregado."""


@dataclass(frozen=True, slots=True)
class BacktestError:
    """Estructura del error de un backtest fallido (F2 §5.2 `error_detail`)."""

    code: str
    message: str
    context: dict[str, Any] | None = None


class Backtest:
    """Agregado raíz. NO usa `@dataclass` porque su estado interno es mutable
    pero controlado por métodos."""

    def __init__(
        self,
        *,
        id: BacktestId,
        name: str,
        created_by: uuid.UUID,
        parameters: BacktestParameters,
        created_at: datetime,
    ) -> None:
        if not name:
            raise ValueError("Backtest.name cannot be empty")
        if created_at.tzinfo is None:
            raise ValueError("Backtest.created_at must be timezone-aware")

        self._id: BacktestId = id
        self._name: str = name
        self._created_by: uuid.UUID = created_by
        self._parameters: BacktestParameters = parameters
        self._created_at: datetime = created_at

        self._status: BacktestStatus = BacktestStatus.PENDING
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._weeks_total: int | None = None
        self._weeks_processed: int | None = None
        self._error: BacktestError | None = None
        self._snapshot: ReproducibilitySnapshot | None = None
        self._result: BacktestResult | None = None

    # ─────────────────────── propiedades de solo lectura ───────────────────────

    @property
    def id(self) -> BacktestId:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def created_by(self) -> uuid.UUID:
        return self._created_by

    @property
    def parameters(self) -> BacktestParameters:
        return self._parameters

    @property
    def status(self) -> BacktestStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def weeks_total(self) -> int | None:
        return self._weeks_total

    @property
    def weeks_processed(self) -> int | None:
        return self._weeks_processed

    @property
    def error(self) -> BacktestError | None:
        return self._error

    @property
    def snapshot(self) -> ReproducibilitySnapshot | None:
        return self._snapshot

    @property
    def result(self) -> BacktestResult | None:
        return self._result

    # ──────────────────────────── transiciones ────────────────────────────

    def start(self, *, when: datetime, weeks_total: int) -> None:
        """PENDING → RUNNING. Fija el número total de semanas para progreso."""
        self._require_status(BacktestStatus.PENDING, "start")
        if when.tzinfo is None:
            raise ValueError("start.when must be timezone-aware")
        # 0 semanas es válido (caso degenerado: ningún run OK en el periodo).
        if weeks_total < 0:
            raise ValueError(f"weeks_total must be non-negative; got {weeks_total}")

        self._status = BacktestStatus.RUNNING
        self._started_at = when
        self._weeks_total = weeks_total
        self._weeks_processed = 0

    def record_progress(self, *, weeks_processed: int) -> None:
        """Actualiza el contador honesto de semanas procesadas (F2 §5.2)."""
        self._require_status(BacktestStatus.RUNNING, "record_progress")
        if self._weeks_total is None:
            raise InvalidStateTransition("weeks_total not set")
        if weeks_processed < 0 or weeks_processed > self._weeks_total:
            raise ValueError(
                f"weeks_processed must be in [0, {self._weeks_total}]; got {weeks_processed}"
            )
        self._weeks_processed = weeks_processed

    def complete(
        self,
        *,
        result: BacktestResult,
        snapshot: ReproducibilitySnapshot,
        when: datetime,
    ) -> None:
        """RUNNING → COMPLETED. **Exige** snapshot y resultado (invariante de
        reproducibilidad: completar sin snapshot rompería F1 §7.1)."""
        self._require_status(BacktestStatus.RUNNING, "complete")
        if when.tzinfo is None:
            raise ValueError("complete.when must be timezone-aware")
        if result is None:
            raise InvalidStateTransition("Cannot complete without result")
        if snapshot is None:
            raise InvalidStateTransition("Cannot complete without snapshot")

        self._status = BacktestStatus.COMPLETED
        self._completed_at = when
        self._result = result
        self._snapshot = snapshot

    def fail(self, *, error: BacktestError, when: datetime) -> None:
        """PENDING|RUNNING → FAILED. Persiste el motivo del fallo."""
        if self._status.is_terminal:
            raise InvalidStateTransition(
                f"Cannot fail from terminal status {self._status.value!r}"
            )
        if when.tzinfo is None:
            raise ValueError("fail.when must be timezone-aware")

        self._status = BacktestStatus.FAILED
        self._completed_at = when
        self._error = error

    def cancel(self, *, when: datetime) -> None:
        """PENDING|RUNNING → CANCELLED (F2 §6.5).

        Si ya es terminal, lanza `InvalidStateTransition` (cara
        `409 not_cancellable` del contrato).
        """
        if self._status.is_terminal:
            raise InvalidStateTransition(
                f"Cannot cancel from terminal status {self._status.value!r}"
            )
        if when.tzinfo is None:
            raise ValueError("cancel.when must be timezone-aware")

        self._status = BacktestStatus.CANCELLED
        self._completed_at = when

    # ──────────────────── Rehidratación desde persistencia ────────────────────

    @classmethod
    def rehydrate(
        cls,
        *,
        id: BacktestId,
        name: str,
        created_by: uuid.UUID,
        parameters: BacktestParameters,
        created_at: datetime,
        status: BacktestStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        weeks_total: int | None = None,
        weeks_processed: int | None = None,
        error: "BacktestError | None" = None,
        snapshot: "ReproducibilitySnapshot | None" = None,
        result: "BacktestResult | None" = None,
    ) -> "Backtest":
        """Reconstruye un agregado a partir de persistencia.

        NO valida transiciones — el repositorio garantiza que el estado
        recuperado es coherente. Saltar el `__init__` (vía `__new__`)
        evita resetear el status a PENDING.
        """
        bt = cls.__new__(cls)
        bt._id = id
        bt._name = name
        bt._created_by = created_by
        bt._parameters = parameters
        bt._created_at = created_at
        bt._status = status
        bt._started_at = started_at
        bt._completed_at = completed_at
        bt._weeks_total = weeks_total
        bt._weeks_processed = weeks_processed
        bt._error = error
        bt._snapshot = snapshot
        bt._result = result
        return bt

    # ─────────────────────────── helpers internos ───────────────────────────

    def _require_status(self, expected: BacktestStatus, op: str) -> None:
        if self._status != expected:
            raise InvalidStateTransition(
                f"Cannot {op} from status {self._status.value!r} "
                f"(expected {expected.value!r})"
            )
