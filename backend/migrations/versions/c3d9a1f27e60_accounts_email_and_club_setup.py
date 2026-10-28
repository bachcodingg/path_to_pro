"""accounts, email, push, calendar, two-step sign-in, club setup and team

Revision ID: c3d9a1f27e60
Revises: b7e1c04a9f3d
Create Date: 2026-10-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9a1f27e60'
down_revision: Union[str, Sequence[str], None] = 'b7e1c04a9f3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_accounts', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('user_accounts', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))
    op.add_column('user_accounts', sa.Column('reminder_hour', sa.Integer(), nullable=True))
    op.add_column('user_accounts', sa.Column('mfa_secret', sa.Text(), nullable=True))
    op.add_column('user_accounts', sa.Column('mfa_enabled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('user_accounts', sa.Column('mfa_recovery', sa.JSON(), nullable=True))
    op.add_column('squads', sa.Column('training_week', sa.JSON(), nullable=True))
    op.create_table('push_subscriptions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('endpoint', sa.String(length=1000), nullable=False),
    sa.Column('p256dh', sa.String(length=200), nullable=False),
    sa.Column('auth', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['user_accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    op.create_index(op.f('ix_push_subscriptions_account_id'), 'push_subscriptions', ['account_id'], unique=False)
    op.create_table('calendar_feeds',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['user_accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('account_id')
    )
    op.create_index(op.f('ix_calendar_feeds_token_hash'), 'calendar_feeds', ['token_hash'], unique=True)
    op.create_table('availability',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('player_id', sa.String(length=36), nullable=False),
    sa.Column('match_id', sa.String(length=36), nullable=True),
    sa.Column('session_id', sa.String(length=36), nullable=True),
    sa.Column('event_key', sa.String(length=50), nullable=False),
    sa.Column('available', sa.Boolean(), nullable=False),
    sa.Column('reason', sa.String(length=20), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('player_id', 'event_key')
    )
    op.create_index(op.f('ix_availability_match_id'), 'availability', ['match_id'], unique=False)
    op.create_index(op.f('ix_availability_player_id'), 'availability', ['player_id'], unique=False)
    op.create_index(op.f('ix_availability_session_id'), 'availability', ['session_id'], unique=False)
    op.create_table('announcements',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('squad_id', sa.String(length=36), nullable=False),
    sa.Column('author_id', sa.String(length=36), nullable=False),
    sa.Column('text', sa.String(length=1000), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['staff_members.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_announcements_created_at'), 'announcements', ['created_at'], unique=False)
    op.create_index(op.f('ix_announcements_squad_id'), 'announcements', ['squad_id'], unique=False)
    op.create_table('auth_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('purpose', sa.String(length=10), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['user_accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auth_tokens_account_id'), 'auth_tokens', ['account_id'], unique=False)
    op.create_index(op.f('ix_auth_tokens_token_hash'), 'auth_tokens', ['token_hash'], unique=True)
    op.create_table('notifications',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('to_email', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('escalation_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('error', sa.String(length=500), nullable=True),
    sa.ForeignKeyConstraint(['escalation_id'], ['escalations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_escalation_id'), 'notifications', ['escalation_id'], unique=False)
    op.create_index(op.f('ix_notifications_sent_at'), 'notifications', ['sent_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_notifications_sent_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_escalation_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_auth_tokens_token_hash'), table_name='auth_tokens')
    op.drop_index(op.f('ix_auth_tokens_account_id'), table_name='auth_tokens')
    op.drop_table('auth_tokens')
    op.drop_index(op.f('ix_announcements_squad_id'), table_name='announcements')
    op.drop_index(op.f('ix_announcements_created_at'), table_name='announcements')
    op.drop_table('announcements')
    op.drop_index(op.f('ix_availability_session_id'), table_name='availability')
    op.drop_index(op.f('ix_availability_player_id'), table_name='availability')
    op.drop_index(op.f('ix_availability_match_id'), table_name='availability')
    op.drop_table('availability')
    op.drop_index(op.f('ix_calendar_feeds_token_hash'), table_name='calendar_feeds')
    op.drop_table('calendar_feeds')
    op.drop_index(op.f('ix_push_subscriptions_account_id'), table_name='push_subscriptions')
    op.drop_table('push_subscriptions')
    op.drop_column('squads', 'training_week')
    op.drop_column('user_accounts', 'mfa_recovery')
    op.drop_column('user_accounts', 'mfa_enabled_at')
    op.drop_column('user_accounts', 'mfa_secret')
    op.drop_column('user_accounts', 'reminder_hour')
    op.drop_column('user_accounts', 'token_version')
    op.drop_column('user_accounts', 'email_verified_at')
