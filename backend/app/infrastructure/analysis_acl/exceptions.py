"""Excepciones de la ACL del Análisis (F1 §7.3, F2 §3, §6.4)."""
from __future__ import annotations


class AnalysisSchemaMismatchError(Exception):
    """El esquema de la BBDD de análisis no coincide con el contrato esperado.

    Esta excepción es la cara visible de la **validación defensiva** (F1 §7.3,
    F2 §3): preferimos fallar claro y diagnosticable a producir resultados
    silenciosamente incorrectos. La API la mapeará a
    `500 analysis_schema_mismatch` (F2 §6.4).
    """

    def __init__(
        self,
        *,
        missing: list[str] | None = None,
        type_mismatches: list[str] | None = None,
    ) -> None:
        self.missing = missing or []
        self.type_mismatches = type_mismatches or []
        parts: list[str] = ["Analysis DB schema does not match expected contract:"]
        if self.missing:
            parts.append(f"  Missing: {', '.join(self.missing)}")
        if self.type_mismatches:
            parts.append(f"  Type mismatch: {', '.join(self.type_mismatches)}")
        super().__init__("\n".join(parts))
