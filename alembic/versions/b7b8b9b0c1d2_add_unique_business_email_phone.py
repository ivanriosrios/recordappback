"""add_unique_business_email_phone

Revision ID: b7b8b9b0c1d2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b7b8b9b0c1d2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar restricciones de unicidad para email y whatsapp_phone en businesses.
    op.create_unique_constraint("uq_businesses_email", "businesses", ["email"])
    op.create_unique_constraint("uq_businesses_whatsapp_phone", "businesses", ["whatsapp_phone"])


def downgrade() -> None:
    op.drop_constraint("uq_businesses_whatsapp_phone", "businesses", type_="unique")
    op.drop_constraint("uq_businesses_email", "businesses", type_="unique")
