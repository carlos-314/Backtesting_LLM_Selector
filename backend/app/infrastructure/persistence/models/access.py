"""Modelo del contexto Acceso (F2 §5.1)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.app_db import Base

# F2 §5.1: dos capacidades efectivas día uno (viewer, analyst);
# `admin` reservado sin capacidades, queda en el enum por previsión.
ALLOWED_ROLES = ("viewer", "analyst", "admin")
_ROLES_SQL = "(" + ", ".join(f"'{r}'" for r in ALLOWED_ROLES) + ")"


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # `google_id` es NULLABLE (ADR-0006): permite pre-alta por admin antes
    # del primer login. UNIQUE conservado: una vez vinculado, no se repite.
    google_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"role IN {_ROLES_SQL}", name="ck_app_user_role"),
    )
