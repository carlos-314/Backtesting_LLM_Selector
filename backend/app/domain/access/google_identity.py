"""`GoogleIdentity` VO (F2 §7.3).

Datos extraídos del `id_token` verificado por Google. El `google_id` es el
campo `sub` del JWT (estable, único por cuenta Google).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    google_id: str
    email: str
    full_name: str | None = None
    picture_url: str | None = None

    def __post_init__(self) -> None:
        if not self.google_id:
            raise ValueError("GoogleIdentity.google_id cannot be empty")
        if not self.email:
            raise ValueError("GoogleIdentity.email cannot be empty")
