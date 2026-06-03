"""Tests de integración de la ACL del Análisis contra Postgres real (F2 §8.3).

Es el test "más valioso" según F2 §8.3: si esto no pasa, F1 §7.3
(validación defensiva) es solo una intención escrita.

BBDD de test: `backtesting_analysis_test` en el mismo Postgres local
(host 55432). Se crea automáticamente; los tests recrean el schema legacy
con un subconjunto curado de los casos sucios deliberados.
"""
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.shared.ticker import TickerSymbol
from app.domain.shared.week import NEW_YORK
from app.infrastructure.analysis_acl.acl_reader import AnalysisAclReader
from app.infrastructure.analysis_acl.exceptions import AnalysisSchemaMismatchError

# ────────────────────────── Fixtures ──────────────────────────

ANALYSIS_TEST_URL = (
    "postgresql+asyncpg://backtesting:backtesting_dev@localhost:55432/backtesting_analysis_test"
)

DDL_CREATE = [
    'DROP TABLE IF EXISTS portfolios',
    'DROP TABLE IF EXISTS analysis_runs',
    """
    CREATE TABLE analysis_runs (
        id_run        integer PRIMARY KEY,
        "fechaRun"    timestamp with time zone,
        run_code      character varying(20),
        descripcion   text,
        status        character varying(50) DEFAULT 'STARTED'
    )
    """,
    """
    CREATE TABLE portfolios (
        id_portfolio  integer PRIMARY KEY,
        id_run        integer,
        ticker        character varying(20),
        nombre        text,
        rol           text
    )
    """,
]


@pytest.fixture
async def analysis_session() -> AsyncIterator[AsyncSession]:
    """Sesión async contra la BBDD de análisis de test, con schema recreado."""
    engine = create_async_engine(ANALYSIS_TEST_URL, echo=False)
    SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        for stmt in DDL_CREATE:
            await conn.execute(text(stmt))

    async with SessionMaker() as s:
        yield s

    await engine.dispose()


async def _insert_run(
    s: AsyncSession,
    *,
    id_run: int,
    fecha_run: datetime,
    run_code: str = "RUN",
    status: str = "COMPLETED",
) -> None:
    await s.execute(
        text(
            'INSERT INTO analysis_runs (id_run, "fechaRun", run_code, status)'
            " VALUES (:id, :fr, :rc, :st)"
        ),
        {"id": id_run, "fr": fecha_run, "rc": run_code, "st": status},
    )


async def _insert_pick(
    s: AsyncSession,
    *,
    id_portfolio: int,
    id_run: int,
    ticker: str | None,
    nombre: str | None = None,
    rol: str | None = None,
) -> None:
    await s.execute(
        text(
            "INSERT INTO portfolios (id_portfolio, id_run, ticker, nombre, rol)"
            " VALUES (:idp, :idr, :tk, :nm, :rl)"
        ),
        {"idp": id_portfolio, "idr": id_run, "tk": ticker, "nm": nombre, "rl": rol},
    )


# ─────────────────────── Validación defensiva (F1 §7.3) ───────────────────────


async def test_acl_validacion_pasa_cuando_schema_es_el_esperado(
    analysis_session: AsyncSession,
) -> None:
    """Sin lanzar, el schema recién creado debe cumplir el contrato."""
    acl = AnalysisAclReader(analysis_session)
    # `list_runs_in_period` valida internamente la primera vez.
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-05"
    )
    assert runs == []


async def test_acl_lanza_schema_mismatch_si_falta_columna(
    analysis_session: AsyncSession,
) -> None:
    """F2 §3, §6.4: si una columna esperada desaparece, fallar claro."""
    await analysis_session.execute(text("ALTER TABLE analysis_runs DROP COLUMN status"))
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    with pytest.raises(AnalysisSchemaMismatchError) as exc_info:
        await acl.list_runs_in_period(
            period_start_iso="2026-01-05", period_end_iso="2026-01-05"
        )
    assert "analysis_runs.status" in str(exc_info.value)


async def test_acl_lanza_schema_mismatch_si_falta_tabla(
    analysis_session: AsyncSession,
) -> None:
    await analysis_session.execute(text("DROP TABLE portfolios"))
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    with pytest.raises(AnalysisSchemaMismatchError) as exc_info:
        await acl.list_runs_in_period(
            period_start_iso="2026-01-05", period_end_iso="2026-01-05"
        )
    assert "table portfolios" in str(exc_info.value)


async def test_acl_lanza_schema_mismatch_si_tipo_no_coincide(
    analysis_session: AsyncSession,
) -> None:
    """Si alguien cambiara `id_run` a bigint, lo detectamos."""
    await analysis_session.execute(text("ALTER TABLE analysis_runs ALTER COLUMN id_run TYPE bigint"))
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    with pytest.raises(AnalysisSchemaMismatchError) as exc_info:
        await acl.list_runs_in_period(
            period_start_iso="2026-01-05", period_end_iso="2026-01-05"
        )
    assert "id_run" in str(exc_info.value)
    assert "expected 'integer'" in str(exc_info.value)


async def test_acl_cachea_validacion_no_repite_information_schema(
    analysis_session: AsyncSession,
) -> None:
    """La validación se hace una vez por instancia, no por cada llamada.

    Prueba: tras una 1ª llamada exitosa, rompemos el schema; una 2ª llamada
    sobre la MISMA instancia ya no re-valida → no lanza
    `AnalysisSchemaMismatchError` (sino el error SQL crudo de la query rota).
    Una instancia NUEVA sí detecta el mismatch.
    """
    from sqlalchemy.exc import ProgrammingError

    acl = AnalysisAclReader(analysis_session)
    await acl.list_runs_in_period(period_start_iso="2026-01-05", period_end_iso="2026-01-05")

    await analysis_session.execute(text("ALTER TABLE analysis_runs DROP COLUMN status"))
    await analysis_session.commit()

    # Misma instancia: NO re-valida (caching). Lanza ProgrammingError porque
    # la query SELECT r.status falla, pero NO AnalysisSchemaMismatchError.
    with pytest.raises(ProgrammingError):
        await acl.list_runs_in_period(
            period_start_iso="2026-01-05", period_end_iso="2026-01-05"
        )

    # Tras una query fallida, la transacción está abortada → rollback.
    await analysis_session.rollback()

    # Instancia nueva: sí valida → AnalysisSchemaMismatchError.
    fresh_acl = AnalysisAclReader(analysis_session)
    with pytest.raises(AnalysisSchemaMismatchError):
        await fresh_acl.list_runs_in_period(
            period_start_iso="2026-01-05", period_end_iso="2026-01-05"
        )


# ─────────────────────── list_runs_in_period ───────────────────────


async def test_acl_list_runs_devuelve_runs_dentro_del_periodo(
    analysis_session: AsyncSession,
) -> None:
    # 3 runs: uno antes del periodo, uno dentro, uno después
    await _insert_run(
        analysis_session, id_run=1,
        fecha_run=datetime(2025, 12, 29, 9, 0, tzinfo=NEW_YORK),  # fuera, antes
    )
    await _insert_run(
        analysis_session, id_run=2,
        fecha_run=datetime(2026, 1, 7, 9, 0, tzinfo=NEW_YORK),  # dentro
    )
    await _insert_run(
        analysis_session, id_run=3,
        fecha_run=datetime(2026, 1, 20, 9, 0, tzinfo=NEW_YORK),  # fuera, después
    )
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-12"
    )
    assert [r.id for r in runs] == [2]


async def test_acl_list_runs_borde_lunes_00_00_NY_inclusivo(
    analysis_session: AsyncSession,
) -> None:
    """Lunes NY 00:00 del periodo_start es el primer instante incluido."""
    await _insert_run(
        analysis_session, id_run=10,
        fecha_run=datetime(2026, 1, 5, 0, 0, tzinfo=NEW_YORK),
    )
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-05"
    )
    assert len(runs) == 1
    assert runs[0].id == 10


async def test_acl_list_runs_borde_lunes_siguiente_00_00_NY_exclusivo(
    analysis_session: AsyncSession,
) -> None:
    """Lunes NY 00:00 inmediato tras periodo_end NO se incluye (semiabierto)."""
    await _insert_run(
        analysis_session, id_run=11,
        fecha_run=datetime(2026, 1, 12, 0, 0, tzinfo=NEW_YORK),
    )
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-05"
    )
    assert runs == []


async def test_acl_list_runs_pick_count_precomputado(
    analysis_session: AsyncSession,
) -> None:
    await _insert_run(
        analysis_session, id_run=20,
        fecha_run=datetime(2026, 1, 6, 9, 0, tzinfo=NEW_YORK),
    )
    for i in range(3):
        await _insert_pick(analysis_session, id_portfolio=100 + i, id_run=20, ticker=f"T{i}")
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-05"
    )
    assert runs[0].pick_count == 3


async def test_acl_list_runs_pick_count_excluye_picks_con_ticker_null(
    analysis_session: AsyncSession,
) -> None:
    """Datos sucios: a veces hay filas en portfolios sin ticker. La regla
    ADR-0004 cuenta picks **útiles**, no filas crudas."""
    await _insert_run(
        analysis_session, id_run=21,
        fecha_run=datetime(2026, 1, 6, 9, 0, tzinfo=NEW_YORK),
    )
    await _insert_pick(analysis_session, id_portfolio=1, id_run=21, ticker="AAPL")
    await _insert_pick(analysis_session, id_portfolio=2, id_run=21, ticker=None)  # basura
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-05"
    )
    assert runs[0].pick_count == 1


async def test_acl_list_runs_orden_por_fecha_run_y_id(
    analysis_session: AsyncSession,
) -> None:
    await _insert_run(
        analysis_session, id_run=30,
        fecha_run=datetime(2026, 1, 9, 9, 0, tzinfo=NEW_YORK),
    )
    await _insert_run(
        analysis_session, id_run=31,
        fecha_run=datetime(2026, 1, 6, 9, 0, tzinfo=NEW_YORK),
    )
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    runs = await acl.list_runs_in_period(
        period_start_iso="2026-01-05", period_end_iso="2026-01-05"
    )
    assert [r.id for r in runs] == [31, 30]  # por fecha asc


# ─────────────────────── get_picks_for_run ───────────────────────


async def test_acl_picks_devuelve_picks_de_ese_run_y_filtra_sucios(
    analysis_session: AsyncSession,
) -> None:
    await _insert_run(
        analysis_session, id_run=40,
        fecha_run=datetime(2026, 1, 6, tzinfo=NEW_YORK),
    )
    await _insert_run(
        analysis_session, id_run=41,
        fecha_run=datetime(2026, 1, 6, tzinfo=NEW_YORK),
    )
    await _insert_pick(analysis_session, id_portfolio=1, id_run=40, ticker="AAPL", rol="core")
    await _insert_pick(analysis_session, id_portfolio=2, id_run=40, ticker="MSFT", rol="hedge")
    await _insert_pick(analysis_session, id_portfolio=3, id_run=40, ticker=None)  # sucio
    await _insert_pick(analysis_session, id_portfolio=4, id_run=40, ticker="   ")  # sucio
    await _insert_pick(analysis_session, id_portfolio=5, id_run=41, ticker="OTHER")
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    picks = await acl.get_picks_for_run(run_id=40)
    assert [str(p.ticker) for p in picks] == ["AAPL", "MSFT"]
    assert picks[0].role == "core"
    assert picks[1].role == "hedge"


async def test_acl_picks_normaliza_ticker_a_TickerSymbol(
    analysis_session: AsyncSession,
) -> None:
    """Casing sucio del legacy: la ACL normaliza al exponer al dominio."""
    await _insert_run(
        analysis_session, id_run=50,
        fecha_run=datetime(2026, 1, 6, tzinfo=NEW_YORK),
    )
    await _insert_pick(analysis_session, id_portfolio=1, id_run=50, ticker="  aapl  ")
    await analysis_session.commit()

    acl = AnalysisAclReader(analysis_session)
    picks = await acl.get_picks_for_run(run_id=50)
    assert picks[0].ticker == TickerSymbol("AAPL")


async def test_acl_picks_run_inexistente_devuelve_lista_vacia(
    analysis_session: AsyncSession,
) -> None:
    acl = AnalysisAclReader(analysis_session)
    assert await acl.get_picks_for_run(run_id=9999) == []
