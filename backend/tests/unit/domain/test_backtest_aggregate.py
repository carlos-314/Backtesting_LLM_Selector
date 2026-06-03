"""Tests del agregado `Backtest` (F2 §4.6, §5.2, §8.2)."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.domain.backtesting.backtest import Backtest, BacktestError, InvalidStateTransition
from app.domain.backtesting.parameters import BacktestParameters, BacktestStatus
from app.domain.backtesting.result import BacktestResult
from app.domain.backtesting.snapshot import ReproducibilitySnapshot
from app.domain.shared.money import Money
from app.domain.shared.week import Week


def _params() -> BacktestParameters:
    return BacktestParameters(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 26)),  # 4 semanas
        initial_capital=Money.usd("10000"),
    )


def _bt(name: str = "BT") -> Backtest:
    return Backtest(
        id=uuid.uuid4(),
        name=name,
        created_by=uuid.uuid4(),
        parameters=_params(),
        created_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
    )


NOW = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)


# ─────────────────────── Construcción ───────────────────────


def test_backtest_recien_creado_esta_pending() -> None:
    bt = _bt()
    assert bt.status == BacktestStatus.PENDING
    assert bt.started_at is None
    assert bt.completed_at is None
    assert bt.weeks_total is None


def test_backtest_name_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="name"):
        _bt(name="")


def test_backtest_created_at_naive_lanza_error() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Backtest(
            id=uuid.uuid4(),
            name="x",
            created_by=uuid.uuid4(),
            parameters=_params(),
            created_at=datetime(2026, 1, 1, 10, 0),  # naive
        )


# ─────────────────────── start ───────────────────────


def test_start_de_pending_pasa_a_running() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    assert bt.status == BacktestStatus.RUNNING
    assert bt.started_at == NOW
    assert bt.weeks_total == 4
    assert bt.weeks_processed == 0


def test_start_dos_veces_lanza_error() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    with pytest.raises(InvalidStateTransition, match="start"):
        bt.start(when=NOW, weeks_total=4)


def test_start_con_weeks_total_negativo_lanza_error() -> None:
    bt = _bt()
    with pytest.raises(ValueError, match="weeks_total"):
        bt.start(when=NOW, weeks_total=-1)


def test_start_con_weeks_total_cero_es_valido() -> None:
    """Caso degenerado: ningún run OK en el periodo. El engine completa con
    snapshot vacío. weeks_total=0 NO es error."""
    bt = _bt()
    bt.start(when=NOW, weeks_total=0)
    assert bt.weeks_total == 0
    assert bt.status == BacktestStatus.RUNNING


def test_start_con_when_naive_lanza_error() -> None:
    bt = _bt()
    with pytest.raises(ValueError, match="timezone-aware"):
        bt.start(when=datetime(2026, 1, 5, 12, 0), weeks_total=4)


# ─────────────────────── record_progress ───────────────────────


def test_record_progress_actualiza_contador() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    bt.record_progress(weeks_processed=2)
    assert bt.weeks_processed == 2


def test_record_progress_en_pending_lanza_error() -> None:
    bt = _bt()
    with pytest.raises(InvalidStateTransition):
        bt.record_progress(weeks_processed=1)


def test_record_progress_fuera_de_rango_lanza_error() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    with pytest.raises(ValueError, match=r"\[0, 4\]"):
        bt.record_progress(weeks_processed=5)
    with pytest.raises(ValueError, match=r"\[0, 4\]"):
        bt.record_progress(weeks_processed=-1)


# ─────────────────────── complete ───────────────────────


def test_complete_de_running_con_result_y_snapshot_pasa_a_completed() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    bt.complete(
        result=BacktestResult(total_return=Decimal("0.05")),
        snapshot=ReproducibilitySnapshot(weeks=()),
        when=NOW,
    )
    assert bt.status == BacktestStatus.COMPLETED
    assert bt.result is not None
    assert bt.snapshot is not None
    assert bt.completed_at == NOW


def test_complete_desde_pending_lanza_error() -> None:
    """Invariante F2: no se completa sin haber pasado por running."""
    bt = _bt()
    with pytest.raises(InvalidStateTransition, match="complete"):
        bt.complete(
            result=BacktestResult(),
            snapshot=ReproducibilitySnapshot(weeks=()),
            when=NOW,
        )


def test_complete_sin_result_lanza_error() -> None:
    """Invariante F1 §7.1: la reproducibilidad exige result+snapshot."""
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    with pytest.raises(InvalidStateTransition, match="without result"):
        bt.complete(
            result=None,  # type: ignore[arg-type]
            snapshot=ReproducibilitySnapshot(weeks=()),
            when=NOW,
        )


def test_complete_sin_snapshot_lanza_error() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    with pytest.raises(InvalidStateTransition, match="without snapshot"):
        bt.complete(
            result=BacktestResult(),
            snapshot=None,  # type: ignore[arg-type]
            when=NOW,
        )


def test_complete_dos_veces_lanza_error() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    bt.complete(
        result=BacktestResult(),
        snapshot=ReproducibilitySnapshot(weeks=()),
        when=NOW,
    )
    with pytest.raises(InvalidStateTransition):
        bt.complete(
            result=BacktestResult(),
            snapshot=ReproducibilitySnapshot(weeks=()),
            when=NOW,
        )


# ─────────────────────── fail ───────────────────────


def test_fail_desde_running_pasa_a_failed_con_error_detail() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    err = BacktestError(code="prices_unavailable", message="yfinance down", context={"ticker": "AAPL"})
    bt.fail(error=err, when=NOW)
    assert bt.status == BacktestStatus.FAILED
    assert bt.error == err
    assert bt.completed_at == NOW


def test_fail_desde_pending_es_legal() -> None:
    """Un backtest puede fallar antes de empezar (p.ej. validación inicial
    del engine antes de start)."""
    bt = _bt()
    bt.fail(error=BacktestError(code="x", message="y"), when=NOW)
    assert bt.status == BacktestStatus.FAILED


def test_fail_desde_terminal_lanza_error() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    bt.complete(
        result=BacktestResult(),
        snapshot=ReproducibilitySnapshot(weeks=()),
        when=NOW,
    )
    with pytest.raises(InvalidStateTransition, match="terminal"):
        bt.fail(error=BacktestError(code="x", message="y"), when=NOW)


# ─────────────────────── cancel ───────────────────────


def test_cancel_desde_pending_pasa_a_cancelled() -> None:
    bt = _bt()
    bt.cancel(when=NOW)
    assert bt.status == BacktestStatus.CANCELLED


def test_cancel_desde_running_pasa_a_cancelled() -> None:
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    bt.cancel(when=NOW)
    assert bt.status == BacktestStatus.CANCELLED


def test_cancel_desde_completed_lanza_error_409_equivalente() -> None:
    """F2 §6.5: cancelar un terminal → 409 not_cancellable."""
    bt = _bt()
    bt.start(when=NOW, weeks_total=4)
    bt.complete(
        result=BacktestResult(),
        snapshot=ReproducibilitySnapshot(weeks=()),
        when=NOW,
    )
    with pytest.raises(InvalidStateTransition, match="terminal"):
        bt.cancel(when=NOW)


def test_cancel_desde_cancelled_lanza_error_idempotencia_NO_silenciosa() -> None:
    """No idempotencia silenciosa: el segundo cancel falla claro."""
    bt = _bt()
    bt.cancel(when=NOW)
    with pytest.raises(InvalidStateTransition, match="terminal"):
        bt.cancel(when=NOW)


# ─────────────────────── Inmutabilidad de campos identificadores ───────────────────────


def test_rehydrate_construye_agregado_en_estado_terminal_sin_pasar_por_transiciones() -> None:
    """El repository necesita poder reconstruir un Backtest COMPLETED leído
    de la BBDD sin re-ejecutar start()/complete()."""
    bt_id = uuid.uuid4()
    user = uuid.uuid4()
    params = _params()
    bt = Backtest.rehydrate(
        id=bt_id,
        name="recuperado",
        created_by=user,
        parameters=params,
        created_at=NOW,
        status=BacktestStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        weeks_total=4,
        weeks_processed=4,
        result=BacktestResult(total_return=Decimal("0.10")),
        snapshot=ReproducibilitySnapshot(weeks=()),
    )
    assert bt.id == bt_id
    assert bt.status == BacktestStatus.COMPLETED
    assert bt.result is not None
    assert bt.weeks_processed == 4


def test_rehydrate_de_failed_preserva_error() -> None:
    bt = Backtest.rehydrate(
        id=uuid.uuid4(),
        name="failed",
        created_by=uuid.uuid4(),
        parameters=_params(),
        created_at=NOW,
        status=BacktestStatus.FAILED,
        completed_at=NOW,
        error=BacktestError(code="prices_unavailable", message="yfinance down"),
    )
    assert bt.status == BacktestStatus.FAILED
    assert bt.error.code == "prices_unavailable"


def test_rehydrate_no_valida_transiciones_acepta_estados_arbitrarios() -> None:
    """Distinto de la API pública: el repositorio carga lo que la BBDD diga,
    sin re-ejecutar el ciclo de vida."""
    bt = Backtest.rehydrate(
        id=uuid.uuid4(),
        name="x",
        created_by=uuid.uuid4(),
        parameters=_params(),
        created_at=NOW,
        status=BacktestStatus.CANCELLED,
        completed_at=NOW,
    )
    assert bt.status == BacktestStatus.CANCELLED


def test_backtest_no_permite_cambiar_id_directamente() -> None:
    """El estado interno es mutable solo a través de los métodos del agregado.
    `_id` con underscore comunica intención; este test verifica que no hay
    setter público."""
    bt = _bt()
    assert not hasattr(bt, "id_setter")
    # `bt.id` no tiene setter:
    with pytest.raises(AttributeError):
        bt.id = uuid.uuid4()  # type: ignore[misc]
