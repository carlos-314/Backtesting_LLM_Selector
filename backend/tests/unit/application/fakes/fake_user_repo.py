"""Fake en memoria de `UserRepository`."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain.access.user import User


@dataclass
class FakeUserRepository:
    _by_id: dict[uuid.UUID, User] = field(default_factory=dict)

    def seed(self, user: User) -> None:
        """Helper de test: inserta directamente sin pasar por save()."""
        self._by_id[user.id] = user

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    async def find_by_google_id(self, google_id: str) -> User | None:
        for u in self._by_id.values():
            if u.google_id == google_id:
                return u
        return None

    async def find_by_email(self, email: str) -> User | None:
        for u in self._by_id.values():
            if u.email == email:
                return u
        return None

    async def list_all(self) -> list[User]:
        return list(self._by_id.values())

    async def save(self, user: User) -> None:
        self._by_id[user.id] = user

    async def link_google_id(self, user_id: uuid.UUID, google_id: str) -> None:
        u = self._by_id[user_id]
        # Reemplaza por nuevo VO con google_id seteado (User es frozen)
        from dataclasses import replace
        self._by_id[user_id] = replace(u, google_id=google_id)
