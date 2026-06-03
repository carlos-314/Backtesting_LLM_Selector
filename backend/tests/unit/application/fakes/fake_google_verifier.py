"""Fake de `GoogleIdentityVerifier`."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.access.exceptions import (
    GoogleUnreachableError,
    InvalidGoogleTokenError,
)
from app.domain.access.google_identity import GoogleIdentity


@dataclass
class FakeGoogleIdentityVerifier:
    """Mapea `id_token` (string ficticio) → `GoogleIdentity`.

    Permite simular tokens inválidos y caída de Google.
    """

    identities: dict[str, GoogleIdentity] = field(default_factory=dict)
    fail_unreachable: bool = False
    verify_calls: list[str] = field(default_factory=list)

    def set_identity(self, token: str, identity: GoogleIdentity) -> None:
        self.identities[token] = identity

    async def verify(self, id_token: str) -> GoogleIdentity:
        self.verify_calls.append(id_token)
        if self.fail_unreachable:
            raise GoogleUnreachableError("Google is down")
        if id_token not in self.identities:
            raise InvalidGoogleTokenError(f"token not recognized: {id_token!r}")
        return self.identities[id_token]
