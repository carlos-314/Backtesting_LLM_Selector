"""Excepciones del contexto Acceso (F2 §6.3)."""
from __future__ import annotations


class InvalidGoogleTokenError(Exception):
    """`id_token` inválido o mal firmado. Mapea a `401 invalid_google_token`."""


class GoogleUnreachableError(Exception):
    """Imposible alcanzar Google para verificar. Mapea a `502 google_unreachable`."""


class UserNotAuthorizedError(Exception):
    """Email no dado de alta o user inactivo. Mapea a `403 user_not_authorized`."""


class EmailAlreadyRegisteredError(Exception):
    """Intento de alta de un email que ya existe. Mapea a `409` o `422` en API."""


class NotPermittedError(Exception):
    """El user no tiene capacidad para esta operación. Mapea a `403`."""
