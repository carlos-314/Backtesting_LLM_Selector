"""Tests unitarios de BacktestParameters y BacktestStatus (F2 §4.6, §5.2)."""
from datetime import date
from decimal import Decimal

import pytest

from app.domain.backtesting.parameters import BacktestParameters, BacktestStatus
from app.domain.shared.money import Money
from app.domain.shared.week import Week


def _params(**overrides) -> BacktestParameters:
    defaults = {
        "period_start": Week(date(2026, 1, 5)),
        "period_end": Week(date(2026, 3, 30)),
        "initial_capital": Money.usd("100000"),
        "strategy_code": "weekly_rotation",
        "benchmark_code": "buy_and_hold",
    }
    defaults.update(overrides)
    return BacktestParameters(**defaults)


# ─────────────────────── BacktestStatus ───────────────────────


def test_status_valores_son_los_5_del_modelo() -> None:
    assert {s.value for s in BacktestStatus} == {
        "pending", "running", "completed", "failed", "cancelled"
    }


def test_status_terminales_son_completed_failed_cancelled() -> None:
    assert BacktestStatus.COMPLETED.is_terminal
    assert BacktestStatus.FAILED.is_terminal
    assert BacktestStatus.CANCELLED.is_terminal


def test_status_no_terminales_son_pending_y_running() -> None:
    assert not BacktestStatus.PENDING.is_terminal
    assert not BacktestStatus.RUNNING.is_terminal


# ─────────────────────── BacktestParameters: validación ───────────────────────


def test_parameters_construye_con_periodo_y_capital_validos() -> None:
    p = _params()
    assert p.weeks_count == 13  # 5/Ene a 30/Mar inclusive = 13 lunes


def test_parameters_period_end_anterior_a_start_lanza_error() -> None:
    with pytest.raises(ValueError, match="period_end .* must be >= period_start"):
        _params(period_start=Week(date(2026, 3, 30)), period_end=Week(date(2026, 1, 5)))


def test_parameters_period_de_una_sola_semana_es_valido() -> None:
    """Caso degenerado pero legal: start == end."""
    w = Week(date(2026, 1, 5))
    p = _params(period_start=w, period_end=w)
    assert p.weeks_count == 1


def test_parameters_capital_cero_lanza_error() -> None:
    with pytest.raises(ValueError, match="initial_capital must be positive"):
        _params(initial_capital=Money(Decimal("0"), "USD"))


def test_parameters_capital_negativo_lanza_error() -> None:
    with pytest.raises(ValueError, match="initial_capital must be positive"):
        _params(initial_capital=Money(Decimal("-1"), "USD"))


def test_parameters_strategy_code_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="strategy_code"):
        _params(strategy_code="")


def test_parameters_benchmark_code_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="benchmark_code"):
        _params(benchmark_code="")


# ─────────────────────── Propiedades derivadas ───────────────────────


def test_parameters_base_currency_se_deriva_del_capital() -> None:
    p = _params(initial_capital=Money(Decimal("1000"), "EUR"))
    assert p.base_currency == "EUR"


def test_parameters_weeks_count_4_semanas() -> None:
    p = _params(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 26)),  # 4 lunes inclusive
    )
    assert p.weeks_count == 4


def test_parameters_iter_weeks_itera_inclusive() -> None:
    p = _params(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 26)),
    )
    weeks = list(p.iter_weeks())
    assert [str(w) for w in weeks] == ["2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26"]


def test_parameters_iter_weeks_periodo_de_una_semana() -> None:
    w = Week(date(2026, 1, 5))
    p = _params(period_start=w, period_end=w)
    assert list(p.iter_weeks()) == [w]


# ─────────────────────── Inmutabilidad e igualdad ───────────────────────


def test_parameters_es_inmutable() -> None:
    p = _params()
    with pytest.raises(Exception):
        p.initial_capital = Money.usd("999")  # type: ignore[misc]


def test_parameters_iguales_y_hashables_con_mismos_valores() -> None:
    a = _params()
    b = _params()
    assert a == b
    assert hash(a) == hash(b)


def test_parameters_defaults_son_strategy_y_benchmark_dia_uno() -> None:
    p = BacktestParameters(
        period_start=Week(date(2026, 1, 5)),
        period_end=Week(date(2026, 1, 12)),
        initial_capital=Money.usd("1000"),
    )
    assert p.strategy_code == "weekly_rotation"
    assert p.benchmark_code == "buy_and_hold"
