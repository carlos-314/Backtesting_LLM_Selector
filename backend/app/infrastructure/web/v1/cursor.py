"""Cursor opaco para paginación (F2 §6.1, auditoría I6/M4).

El cursor codifica un payload arbitrario en base64-urlsafe sobre JSON.
**Opaco**: el cliente NO debe inspeccionar ni construir cursores; solo
pasarlos tal cual al backend.
"""
from __future__ import annotations

import base64
import json
from typing import Any


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Descodifica un cursor opaco. Lanza `ValueError` si no es válido."""
    # Restaurar padding base64
    padding = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid cursor: {exc}") from exc
