"""Tests unitarios del VO `Week` (F2 §4.3, §8.1, §8.7).

Convención de nombres: `test_<unidad>_<condición>_<resultado>` (F2 §8.7).
Cada test se lee como la regla que afirma. Sin BBDD, sin red.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.domain.shared.week import NEW_YORK, Week


# ────────────────────── Construcción y validación ──────────────────────


def test_week_construida_con_lunes_es_valida() -> None:
    w = Week(week_date=date(2026, 1, 5))  # 2026-01-05 es lunes
    assert w.week_date == date(2026, 1, 5)


def test_week_construida_con_dia_no_lunes_lanza_error() -> None:
    with pytest.raises(ValueError, match="must be a Monday"):
        Week(week_date=date(2026, 1, 6))  # martes


def test_week_construida_con_domingo_lanza_error() -> None:
    with pytest.raises(ValueError, match="must be a Monday"):
        Week(week_date=date(2026, 1, 4))


def test_week_from_iso_lunes_construye() -> None:
    assert Week.from_iso("2026-01-05").week_date == date(2026, 1, 5)


def test_week_from_iso_no_lunes_lanza_error() -> None:
    with pytest.raises(ValueError, match="must be a Monday"):
        Week.from_iso("2026-01-06")


# ──────────────────────────── from_instant ────────────────────────────


def test_week_from_instant_lunes_mismo_dia_devuelve_misma_semana() -> None:
    # Lunes 2026-01-05 10:00 NY → semana 2026-01-05
    instant = datetime(2026, 1, 5, 10, 0, tzinfo=NEW_YORK)
    assert Week.from_instant(instant).week_date == date(2026, 1, 5)


def test_week_from_instant_miercoles_devuelve_lunes_de_esa_semana() -> None:
    instant = datetime(2026, 1, 7, 14, 30, tzinfo=NEW_YORK)
    assert Week.from_instant(instant).week_date == date(2026, 1, 5)


def test_week_from_instant_domingo_devuelve_lunes_anterior() -> None:
    """Domingo está en la semana del lunes anterior según F2 §4.3."""
    instant = datetime(2026, 1, 11, 23, 0, tzinfo=NEW_YORK)
    assert Week.from_instant(instant).week_date == date(2026, 1, 5)


def test_week_from_instant_lunes_00_00_NY_es_la_propia_semana() -> None:
    """Borde inferior incluido."""
    instant = datetime(2026, 1, 5, 0, 0, tzinfo=NEW_YORK)
    assert Week.from_instant(instant).week_date == date(2026, 1, 5)


def test_week_from_instant_domingo_23_59_madrid_pertenece_a_semana_anterior_en_NY() -> None:
    """Caso clave F2 §4.3: alinear con NY evita que un run nocturno europeo
    caiga en la semana equivocada.

    Madrid (Europe/Madrid) está en CET (UTC+1) en enero. Domingo 11 a las
    23:59 Madrid = 17:59 NY mismo domingo → semana del lunes anterior.
    """
    madrid = ZoneInfo("Europe/Madrid")
    instant_madrid = datetime(2026, 1, 11, 23, 59, tzinfo=madrid)
    assert Week.from_instant(instant_madrid).week_date == date(2026, 1, 5)


def test_week_from_instant_lunes_04_00_madrid_aun_es_domingo_en_NY() -> None:
    """Inverso: el lunes muy temprano en Madrid todavía es domingo en NY,
    así que cae en la semana anterior.

    Lunes 12 a las 04:00 Madrid (CET) = 22:00 domingo NY → semana del lunes
    anterior (2026-01-05).
    """
    madrid = ZoneInfo("Europe/Madrid")
    instant_madrid = datetime(2026, 1, 12, 4, 0, tzinfo=madrid)
    assert Week.from_instant(instant_madrid).week_date == date(2026, 1, 5)


def test_week_from_instant_naive_lanza_error() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Week.from_instant(datetime(2026, 1, 5, 12, 0))


def test_week_from_instant_utc_se_convierte_a_NY() -> None:
    """16:00 UTC del domingo 4 enero = 11:00 NY del domingo → semana anterior."""
    instant_utc = datetime(2026, 1, 4, 16, 0, tzinfo=timezone.utc)
    assert Week.from_instant(instant_utc).week_date == date(2025, 12, 29)


# ─────────────────────── start_ny / end_ny / contains ───────────────────────


def test_week_start_ny_es_lunes_00_00_NY() -> None:
    w = Week(date(2026, 1, 5))
    assert w.start_ny == datetime(2026, 1, 5, 0, 0, tzinfo=NEW_YORK)


def test_week_end_ny_es_lunes_siguiente_00_00_NY() -> None:
    w = Week(date(2026, 1, 5))
    assert w.end_ny == datetime(2026, 1, 12, 0, 0, tzinfo=NEW_YORK)


def test_week_contains_lunes_00_00_NY_es_verdadero() -> None:
    w = Week(date(2026, 1, 5))
    assert w.contains(datetime(2026, 1, 5, 0, 0, tzinfo=NEW_YORK)) is True


def test_week_contains_lunes_siguiente_00_00_NY_es_falso() -> None:
    """Intervalo semiabierto: el límite superior se excluye."""
    w = Week(date(2026, 1, 5))
    assert w.contains(datetime(2026, 1, 12, 0, 0, tzinfo=NEW_YORK)) is False


def test_week_contains_instante_en_otra_zona_horaria() -> None:
    """Si el instante está en otra TZ, se convierte a NY antes de comprobar."""
    madrid = ZoneInfo("Europe/Madrid")
    # Domingo 11 23:59 Madrid = 17:59 NY domingo → SÍ está en la semana del 5
    w = Week(date(2026, 1, 5))
    assert w.contains(datetime(2026, 1, 11, 23, 59, tzinfo=madrid)) is True


def test_week_contains_naive_lanza_error() -> None:
    w = Week(date(2026, 1, 5))
    with pytest.raises(ValueError, match="timezone-aware"):
        w.contains(datetime(2026, 1, 5, 12, 0))


# ─────────────────────────── next / previous ───────────────────────────


def test_week_next_avanza_siete_dias() -> None:
    assert Week(date(2026, 1, 5)).next().week_date == date(2026, 1, 12)


def test_week_previous_retrocede_siete_dias() -> None:
    assert Week(date(2026, 1, 5)).previous().week_date == date(2025, 12, 29)


def test_week_next_y_previous_son_inversas() -> None:
    w = Week(date(2026, 3, 16))
    assert w.next().previous() == w
    assert w.previous().next() == w


def test_week_next_atraviesa_cambio_horario_DST_sin_romperse() -> None:
    """Cambio de DST en NY = segundo domingo de marzo (15 marzo 2026)."""
    w_before = Week(date(2026, 3, 9))  # antes del cambio
    w_after = w_before.next()
    assert w_after.week_date == date(2026, 3, 16)


# ─────────────────────── Inmutabilidad e igualdad ───────────────────────


def test_week_es_inmutable() -> None:
    w = Week(date(2026, 1, 5))
    with pytest.raises(Exception):  # FrozenInstanceError en runtime
        w.week_date = date(2026, 1, 12)  # type: ignore[misc]


def test_week_misma_fecha_es_igual_y_hashable() -> None:
    a = Week(date(2026, 1, 5))
    b = Week(date(2026, 1, 5))
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_week_str_es_iso_de_la_fecha() -> None:
    assert str(Week(date(2026, 1, 5))) == "2026-01-05"
