"""Rol del usuario (F2 §5.1, F0).

Tres valores cerrados:
- `viewer`: lee screening y backtests, no crea ni cancela.
- `analyst`: además crea/cancela backtests.
- `admin`: además da de alta usuarios y asigna roles (ADR-0006).

Día uno F3 §5.5 dice que `admin` UI ve lo mismo que `analyst`; aquí el
backend distingue por la **capacidad** de gestionar usuarios.
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"
