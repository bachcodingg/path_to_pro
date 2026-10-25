"""guardian alerts

Revision ID: b7e1c04a9f3d
Revises: 921d5d9fca68
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1c04a9f3d'
down_revision: Union[str, Sequence[str], None] = '921d5d9fca68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('guardian_alerts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('player_id', sa.String(length=36), nullable=False),
    sa.Column('guardian_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['guardian_id'], ['guardians.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guardian_alerts_guardian_id'), 'guardian_alerts', ['guardian_id'], unique=False)
    op.create_index(op.f('ix_guardian_alerts_player_id'), 'guardian_alerts', ['player_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_guardian_alerts_player_id'), table_name='guardian_alerts')
    op.drop_index(op.f('ix_guardian_alerts_guardian_id'), table_name='guardian_alerts')
    op.drop_table('guardian_alerts')
