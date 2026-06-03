"""Implementación real del `GoogleIdentityVerifier` (F2 §7.3).

Usa `google-auth` para verificar un id_token contra la public key de Google.
Es el ÚNICO sitio del backend que conoce esa API.
"""
from __future__ import annotations

import logging

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.domain.access.exceptions import (
    GoogleUnreachableError,
    InvalidGoogleTokenError,
)
from app.domain.access.google_identity import GoogleIdentity

log = logging.getLogger(__name__)


class GoogleIdentityVerifierImpl:
    """Verifica un `id_token` contra Google con el `GOOGLE_CLIENT_ID` esperado."""

    def __init__(self, google_client_id: str) -> None:
        if not google_client_id:
            raise ValueError("google_client_id is required")
        self._client_id = google_client_id

    async def verify(self, id_token: str) -> GoogleIdentity:
        # `google-auth` es síncrono. La llamada a su pubkey se cachea
        # internamente; cargas posteriores son rápidas. No envolvemos en
        # to_thread para mantener simplicidad — el coste es bajo.
        try:
            payload = google_id_token.verify_oauth2_token(
                id_token, google_requests.Request(), self._client_id
            )
        except TransportError as exc:
            log.warning("google_verifier: transport error (%s)", exc)
            raise GoogleUnreachableError(str(exc)) from exc
        except (GoogleAuthError, ValueError) as exc:
            log.info("google_verifier: invalid token (%s)", exc)
            raise InvalidGoogleTokenError(str(exc)) from exc

        try:
            return GoogleIdentity(
                google_id=str(payload["sub"]),
                email=str(payload["email"]),
                full_name=payload.get("name"),
                picture_url=payload.get("picture"),
            )
        except KeyError as exc:
            raise InvalidGoogleTokenError(f"Missing field in id_token: {exc}") from exc
