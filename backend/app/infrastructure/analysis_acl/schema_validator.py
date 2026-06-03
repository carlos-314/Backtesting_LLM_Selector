"""Validación defensiva del schema de la BBDD de análisis (F1 §7.3, F2 §3).

Compara `information_schema.columns` contra el contrato cerrado de columnas
y tipos que la ACL espera. Si una columna falta o el tipo no coincide,
lanza `AnalysisSchemaMismatchError`.

Tipos esperados — derivados de la inspección real del schema legacy (ver
memoria `project_legacy_db_railway.md`) ejecutada en ADR-0004:

- `analysis_runs.id_run` → integer
- `analysis_runs.fechaRun` → timestamp with time zone
- `analysis_runs.run_code` → character varying
- `analysis_runs.status` → character varying
- `portfolios.id_run` → integer
- `portfolios.ticker` → character varying
- `portfolios.nombre` → text
- `portfolios.rol` → text

Si el pipeline externo añade columnas, no pasa nada — solo importan las
listadas. Si renombra o cambia un tipo, este validador lo detecta antes de
que produzcamos resultados incorrectos.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.analysis_acl.exceptions import AnalysisSchemaMismatchError

EXPECTED_COLUMNS: dict[str, dict[str, str]] = {
    "analysis_runs": {
        "id_run": "integer",
        "fechaRun": "timestamp with time zone",
        "run_code": "character varying",
        "status": "character varying",
    },
    "portfolios": {
        "id_run": "integer",
        "ticker": "character varying",
        "nombre": "text",
        "rol": "text",
    },
}


async def validate_analysis_schema(session: AsyncSession) -> None:
    """Lanza `AnalysisSchemaMismatchError` si el schema no encaja.

    No es reentrante: el llamador suele cachear el resultado para no
    consultar `information_schema` en cada petición.
    """
    sql = text("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN ('analysis_runs', 'portfolios')
    """)
    result = await session.execute(sql)

    actual: dict[str, dict[str, str]] = {}
    for row in result:
        actual.setdefault(row.table_name, {})[row.column_name] = row.data_type

    missing: list[str] = []
    type_mismatches: list[str] = []

    for table, cols in EXPECTED_COLUMNS.items():
        if table not in actual:
            missing.append(f"table {table}")
            continue
        for col, expected_type in cols.items():
            if col not in actual[table]:
                missing.append(f"{table}.{col}")
                continue
            got = actual[table][col]
            if got != expected_type:
                type_mismatches.append(
                    f"{table}.{col}: expected {expected_type!r}, got {got!r}"
                )

    if missing or type_mismatches:
        raise AnalysisSchemaMismatchError(missing=missing, type_mismatches=type_mismatches)
