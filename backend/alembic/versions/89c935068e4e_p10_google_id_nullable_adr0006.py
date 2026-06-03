"""p10_google_id_nullable_adr0006

ADR-0006: `app_user.google_id` pasa a NULLABLE para permitir pre-alta por
admin antes del primer login. UNIQUE se conserva.

Revision ID: 89c935068e4e
Revises: e332ea7d1de0
Create Date: 2026-06-03 14:28:20.590183
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '89c935068e4e'
down_revision: Union[str, None] = 'e332ea7d1de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'app_user',
        'google_id',
        existing_type=sa.VARCHAR(),
        nullable=True,
    )


def downgrade() -> None:
    # NOTA: el downgrade fallará si hay rows con google_id NULL (no-vinculadas).
    # Es responsabilidad del operador decidir qué hacer con esas filas antes
    # de hacer downgrade.
    op.alter_column(
        'app_user',
        'google_id',
        existing_type=sa.VARCHAR(),
        nullable=False,
    )
