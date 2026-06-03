"""Tests unitarios del `WeekResolver` (F2 §4.7, §8.1, §8.2, ADR-0004).

Sin BBDD ni red — el resolver es puro. Verifica:
- La regla "OK" del ADR-0004 (las tres ramas NO-OK).
- "Último run OK gana" intra-semana.
- Semana sin ningún OK se descarta.
- Logging estructurado con reason por cada descarte.
"""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.screening.read_models import AnalysisRun
from app.domain.screening.week_resolver import (
    REASON_NO_PICKS,
    REASON_STATUS_NOT_COMPLETED,
    REASON_STATUS_UNKNOWN_FAILSAFE,
    WeekResolver,
)
from app.domain.shared.week import NEW_YORK, Week

# Lunes 2026-01-05 en NY, midday → semana del 2026-01-05
MONDAY_05 = datetime(2026, 1, 5, 12, 0, tzinfo=NEW_YORK)
TUESDAY_06 = datetime(2026, 1, 6, 12, 0, tzinfo=NEW_YORK)
FRIDAY_09 = datetime(2026, 1, 9, 12, 0, tzinfo=NEW_YORK)
NEXT_MONDAY_12 = datetime(2026, 1, 12, 12, 0, tzinfo=NEW_YORK)


def _run(
    id: int = 1,
    fecha_run: datetime = MONDAY_05,
    run_code: str = "RUN_TEST",
    status: str = "COMPLETED",
    pick_count: int = 5,
) -> AnalysisRun:
    return AnalysisRun(
        id=id, fecha_run=fecha_run, run_code=run_code, status=status, pick_count=pick_count
    )


# ─────────────────────── Regla "OK" (ADR-0004) ───────────────────────


def test_resolver_run_completed_con_picks_es_ok() -> None:
    assert WeekResolver.is_ok(_run(status="COMPLETED", pick_count=5)) is True


def test_resolver_run_completed_sin_picks_es_no_ok() -> None:
    """ADR-0004: la condición 2 atrapa runs COMPLETED corruptos."""
    assert WeekResolver.is_ok(_run(status="COMPLETED", pick_count=0)) is False


def test_resolver_run_started_es_no_ok() -> None:
    assert WeekResolver.is_ok(_run(status="STARTED", pick_count=5)) is False


def test_resolver_run_status_completed_minusculas_es_no_ok() -> None:
    """ADR-0004: comparación case-sensitive literal."""
    assert WeekResolver.is_ok(_run(status="completed", pick_count=5)) is False


def test_resolver_status_desconocido_es_no_ok_failsafe() -> None:
    """F2 §3.1: cualquier valor no reconocido → NO OK (fail-safe)."""
    assert WeekResolver.is_ok(_run(status="UNKNOWN_FUTURE", pick_count=5)) is False


# ─────────────────────── resolve_weeks: caminos felices ───────────────────────


def test_resolver_un_run_OK_resuelve_su_semana() -> None:
    runs = [_run(id=1, fecha_run=MONDAY_05)]
    result = WeekResolver.resolve_weeks(runs)
    assert result == {Week(date(2026, 1, 5)): runs[0]}


def test_resolver_runs_en_semanas_distintas_resuelven_independientemente() -> None:
    r1 = _run(id=1, fecha_run=MONDAY_05)
    r2 = _run(id=2, fecha_run=NEXT_MONDAY_12)
    result = WeekResolver.resolve_weeks([r1, r2])
    assert result == {
        Week(date(2026, 1, 5)): r1,
        Week(date(2026, 1, 12)): r2,
    }


def test_resolver_lista_vacia_devuelve_diccionario_vacio() -> None:
    assert WeekResolver.resolve_weeks([]) == {}


# ─────────────────────── "Último run OK gana" intra-semana ───────────────────────


def test_resolver_dos_runs_OK_misma_semana_gana_el_mas_reciente() -> None:
    """F2 §1: "si hay dos runs en la misma semana, la semana resuelve al último OK"."""
    older = _run(id=1, fecha_run=MONDAY_05)
    newer = _run(id=2, fecha_run=FRIDAY_09)
    result = WeekResolver.resolve_weeks([older, newer])
    assert result == {Week(date(2026, 1, 5)): newer}


def test_resolver_dos_runs_OK_orden_de_iteracion_no_importa() -> None:
    """El ganador es el más reciente independientemente del orden de entrada."""
    older = _run(id=1, fecha_run=MONDAY_05)
    newer = _run(id=2, fecha_run=FRIDAY_09)
    a = WeekResolver.resolve_weeks([older, newer])
    b = WeekResolver.resolve_weeks([newer, older])
    assert a == b == {Week(date(2026, 1, 5)): newer}


def test_resolver_run_NO_OK_mas_reciente_no_desplaza_a_run_OK_anterior() -> None:
    """Caso crítico: un STARTED reciente no debe pisar a un COMPLETED anterior."""
    ok_older = _run(id=1, fecha_run=MONDAY_05, status="COMPLETED", pick_count=5)
    not_ok_newer = _run(id=2, fecha_run=FRIDAY_09, status="STARTED", pick_count=0)
    result = WeekResolver.resolve_weeks([ok_older, not_ok_newer])
    assert result == {Week(date(2026, 1, 5)): ok_older}


def test_resolver_solo_NO_OK_en_la_semana_descarta_la_semana() -> None:
    """ADR-0004: la semana queda sin run resuelto y no aparece en el resultado."""
    runs = [
        _run(id=1, fecha_run=MONDAY_05, status="STARTED", pick_count=5),
        _run(id=2, fecha_run=TUESDAY_06, status="COMPLETED", pick_count=0),  # no picks
        _run(id=3, fecha_run=FRIDAY_09, status="MYSTERY", pick_count=10),  # failsafe
    ]
    result = WeekResolver.resolve_weeks(runs)
    assert result == {}


# ───────────────────────── Casos de borde temporales ─────────────────────────


def test_resolver_runs_en_lunes_y_domingo_anterior_caen_en_misma_semana_NY() -> None:
    """Domingo 23h NY pertenece a la semana del lunes anterior (F2 §4.3)."""
    sunday_11 = datetime(2026, 1, 11, 23, 0, tzinfo=NEW_YORK)  # semana del 5
    monday_05 = MONDAY_05  # semana del 5
    r_sun = _run(id=1, fecha_run=sunday_11)
    r_mon = _run(id=2, fecha_run=monday_05)
    result = WeekResolver.resolve_weeks([r_sun, r_mon])
    # El domingo 11 es más reciente que el lunes 5 → gana r_sun
    assert result == {Week(date(2026, 1, 5)): r_sun}


def test_resolver_run_naive_lanza_error_al_construir_AnalysisRun() -> None:
    """Defensa en profundidad: el read-model rechaza fechas naive."""
    with pytest.raises(ValueError, match="timezone-aware"):
        AnalysisRun(
            id=1,
            fecha_run=datetime(2026, 1, 5, 12, 0),  # naive
            run_code="X",
            status="COMPLETED",
            pick_count=5,
        )


# ─────────────────────── Logging estructurado (F2 §7.1) ───────────────────────


def test_resolver_loguea_status_not_completed_para_run_started(caplog) -> None:
    caplog.set_level(logging.INFO)
    runs = [_run(id=42, status="STARTED", pick_count=5)]
    WeekResolver.resolve_weeks(runs)
    matching = [r for r in caplog.records if getattr(r, "event", None) == "run_not_ok"]
    assert len(matching) == 1
    assert matching[0].id_run == 42
    assert matching[0].reason == REASON_STATUS_NOT_COMPLETED


def test_resolver_loguea_no_picks_para_run_completed_sin_picks(caplog) -> None:
    caplog.set_level(logging.INFO)
    runs = [_run(id=43, status="COMPLETED", pick_count=0)]
    WeekResolver.resolve_weeks(runs)
    matching = [r for r in caplog.records if getattr(r, "event", None) == "run_not_ok"]
    assert len(matching) == 1
    assert matching[0].reason == REASON_NO_PICKS


def test_resolver_loguea_failsafe_para_status_desconocido(caplog) -> None:
    caplog.set_level(logging.INFO)
    runs = [_run(id=44, status="UNEXPECTED", pick_count=5)]
    WeekResolver.resolve_weeks(runs)
    matching = [r for r in caplog.records if getattr(r, "event", None) == "run_not_ok"]
    assert len(matching) == 1
    assert matching[0].reason == REASON_STATUS_UNKNOWN_FAILSAFE


def test_resolver_no_loguea_runs_OK(caplog) -> None:
    caplog.set_level(logging.INFO)
    WeekResolver.resolve_weeks([_run(id=1)])
    assert not [r for r in caplog.records if getattr(r, "event", None) == "run_not_ok"]


def test_resolver_loguea_todos_los_descartes_en_una_misma_semana(caplog) -> None:
    """Si hay varios NO-OK en la misma semana, todos se loguean (no solo uno)."""
    caplog.set_level(logging.INFO)
    runs = [
        _run(id=1, fecha_run=MONDAY_05, status="STARTED", pick_count=0),
        _run(id=2, fecha_run=TUESDAY_06, status="COMPLETED", pick_count=0),
    ]
    WeekResolver.resolve_weeks(runs)
    matching = [r for r in caplog.records if getattr(r, "event", None) == "run_not_ok"]
    assert {r.id_run for r in matching} == {1, 2}


# ───────────────────────── Pureza ─────────────────────────


def test_resolver_no_muta_su_entrada() -> None:
    """Los read-models son frozen; el resolver no podría mutarlos aunque quisiera."""
    runs = [_run(id=1), _run(id=2, fecha_run=NEXT_MONDAY_12)]
    snapshot = list(runs)
    WeekResolver.resolve_weeks(runs)
    assert runs == snapshot
