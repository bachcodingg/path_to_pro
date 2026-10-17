"""positions, self-guided pathway and guardian invites

Revision ID: 50003b1866d8
Revises: efaf83948259
Create Date: 2026-10-17 22:37:11.356983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import domain.crypto


# revision identifiers, used by Alembic.
revision: str = '50003b1866d8'
down_revision: Union[str, Sequence[str], None] = 'efaf83948259'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('amateur_profiles',
    sa.Column('player_id', sa.String(length=36), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('level_since', sa.Date(), nullable=False),
    sa.Column('goal', sa.String(length=30), nullable=False),
    sa.Column('equipment', sa.String(length=10), nullable=False),
    sa.Column('team_days', sa.JSON(), nullable=False),
    sa.Column('match_day', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('player_id')
    )
    op.add_column('guardians', sa.Column('invite_code', sa.String(length=20), nullable=True))
    op.create_index('ix_guardians_invite_code', 'guardians', ['invite_code'], unique=True)
    # Existing players are academy players; position defaults to midfielder until staff set it.
    op.add_column('players', sa.Column('position', sa.String(length=20), nullable=False, server_default='midfielder'))
    op.add_column('players', sa.Column('pathway', sa.String(length=20), nullable=False, server_default='academy'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('players') as batch:
        batch.drop_column('pathway')
        batch.drop_column('position')
    op.drop_index('ix_guardians_invite_code', table_name='guardians')
    with op.batch_alter_table('guardians') as batch:
        batch.drop_column('invite_code')
    op.drop_table('amateur_profiles')
