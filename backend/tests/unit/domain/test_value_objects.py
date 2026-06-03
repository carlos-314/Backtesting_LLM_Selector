"""Tests unitarios de Money y TickerSymbol (F2 §4.6, §8.1)."""
from decimal import Decimal

import pytest

from app.domain.shared.money import CurrencyMismatchError, Money
from app.domain.shared.ticker import TickerSymbol


# ═══════════════════════════════ Money ═══════════════════════════════


# ─────────────────── Construcción y validación ───────────────────


def test_money_construye_con_decimal_y_currency_3_letras() -> None:
    m = Money(Decimal("100.50"), "USD")
    assert m.amount == Decimal("100.50")
    assert m.currency == "USD"


def test_money_amount_no_decimal_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        Money(100.50, "USD")  # float, no Decimal  # type: ignore[arg-type]


def test_money_amount_int_directo_es_rechazado_para_evitar_ambiguedad() -> None:
    """`amount` debe ser Decimal explícito; aceptar int silenciosamente
    induce errores cuando se mezclan tipos."""
    with pytest.raises(TypeError, match="Decimal"):
        Money(100, "USD")  # type: ignore[arg-type]


def test_money_currency_minusculas_lanza_error() -> None:
    with pytest.raises(ValueError, match="ISO-4217"):
        Money(Decimal("1"), "usd")


def test_money_currency_dos_letras_lanza_error() -> None:
    with pytest.raises(ValueError, match="ISO-4217"):
        Money(Decimal("1"), "US")


def test_money_currency_con_numeros_lanza_error() -> None:
    with pytest.raises(ValueError, match="ISO-4217"):
        Money(Decimal("1"), "US1")


def test_money_factory_usd_construye_con_decimal() -> None:
    m = Money.usd("100")
    assert m == Money(Decimal("100"), "USD")


# ───────────────────────── Aritmética ─────────────────────────


def test_money_suma_misma_divisa_devuelve_misma_divisa() -> None:
    a = Money(Decimal("100"), "USD")
    b = Money(Decimal("50"), "USD")
    assert a + b == Money(Decimal("150"), "USD")


def test_money_suma_distinta_divisa_lanza_error() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("100"), "USD") + Money(Decimal("100"), "EUR")


def test_money_resta_misma_divisa() -> None:
    assert Money.usd("100") - Money.usd("30") == Money.usd("70")


def test_money_resta_distinta_divisa_lanza_error() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money.usd("100") - Money(Decimal("1"), "EUR")


def test_money_multiplica_por_decimal_escalar() -> None:
    assert Money.usd("100") * Decimal("1.5") == Money.usd("150.0")


def test_money_multiplica_por_int_escalar() -> None:
    assert Money.usd("100") * 3 == Money.usd("300")


def test_money_multiplica_por_float_lanza_typeerror() -> None:
    """Evitar pérdida silenciosa de precisión: 0.1 * 3 != 0.3 en float."""
    with pytest.raises(TypeError, match="float"):
        Money.usd("100") * 0.5  # type: ignore[operator]


def test_money_multiplicacion_es_conmutativa_con_escalar_a_la_izquierda() -> None:
    assert Decimal("2") * Money.usd("50") == Money.usd("100")


def test_money_negacion() -> None:
    assert -Money.usd("100") == Money(Decimal("-100"), "USD")


# ───────────────────────── Comparaciones ─────────────────────────


def test_money_comparacion_misma_divisa() -> None:
    assert Money.usd("100") < Money.usd("200")
    assert Money.usd("100") <= Money.usd("100")
    assert Money.usd("200") > Money.usd("100")
    assert Money.usd("100") >= Money.usd("100")


def test_money_comparacion_distinta_divisa_lanza_error() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money.usd("100") < Money(Decimal("100"), "EUR")


# ───────────────────────── Inmutabilidad e igualdad ─────────────────────────


def test_money_es_inmutable() -> None:
    m = Money.usd("100")
    with pytest.raises(Exception):
        m.amount = Decimal("999")  # type: ignore[misc]


def test_money_misma_amount_y_currency_son_iguales_y_hashables() -> None:
    a = Money.usd("100")
    b = Money(Decimal("100"), "USD")
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_money_distinta_divisa_no_es_igual() -> None:
    assert Money(Decimal("100"), "USD") != Money(Decimal("100"), "EUR")


# ═══════════════════════════ TickerSymbol ═══════════════════════════


def test_ticker_construye_con_simbolo_uppercase() -> None:
    assert TickerSymbol("AAPL").value == "AAPL"


def test_ticker_construye_directo_con_minusculas_lanza_error() -> None:
    """Constructor estricto: forzar el uso de `of` para normalizar."""
    with pytest.raises(ValueError, match="uppercase"):
        TickerSymbol("aapl")


def test_ticker_of_normaliza_uppercase_y_trim() -> None:
    assert TickerSymbol.of("  aapl  ") == TickerSymbol("AAPL")


def test_ticker_acepta_punto_para_clases_de_accion() -> None:
    """Tickers reales como BRK.B (Berkshire clase B)."""
    assert TickerSymbol("BRK.B").value == "BRK.B"


def test_ticker_acepta_guion() -> None:
    assert TickerSymbol("MERV-A").value == "MERV-A"


def test_ticker_acepta_alfanumerico() -> None:
    assert TickerSymbol("M3").value == "M3"


def test_ticker_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="empty"):
        TickerSymbol("")


def test_ticker_demasiado_largo_lanza_error() -> None:
    with pytest.raises(ValueError, match="too long"):
        TickerSymbol("A" * 21)


def test_ticker_con_caracteres_invalidos_lanza_error() -> None:
    for bad in ("AAP$", "AAP L", "AA/PL", "A!PL"):
        with pytest.raises(ValueError, match="invalid character"):
            TickerSymbol(bad)


def test_ticker_empieza_con_punto_lanza_error() -> None:
    with pytest.raises(ValueError, match="cannot start or end"):
        TickerSymbol(".AAPL")


def test_ticker_termina_con_guion_lanza_error() -> None:
    with pytest.raises(ValueError, match="cannot start or end"):
        TickerSymbol("AAPL-")


def test_ticker_es_inmutable() -> None:
    t = TickerSymbol("AAPL")
    with pytest.raises(Exception):
        t.value = "MSFT"  # type: ignore[misc]


def test_ticker_mismo_valor_es_igual_y_hashable() -> None:
    a = TickerSymbol("AAPL")
    b = TickerSymbol.of("aapl")
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_ticker_str_es_su_valor() -> None:
    assert str(TickerSymbol("MSFT")) == "MSFT"
