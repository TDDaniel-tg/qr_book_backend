"""Initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-11-07
"""

from alembic import op
import sqlalchemy as sa


revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    room_type_enum = sa.Enum('public', 'admin', 'service', name='roomtype')
    reservation_status_enum = sa.Enum(
        'active',
        'finished',
        'cancelled',
        name='reservationstatus',
    )
    user_role_enum = sa.Enum('student', 'teacher', 'admin', name='userrole')
    audit_action_enum = sa.Enum(
        'create_reservation',
        'cancel_reservation',
        'update_reservation',
        'update_room',
        'create_user',
        'login',
        'logout',
        name='auditaction',
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('role', user_role_enum, nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'rooms',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('type', room_type_enum, nullable=False),
        sa.Column('qr_code_url', sa.String(length=512)),
        sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'reservations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('status', reservation_status_enum, nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('room_id', 'start_time', 'end_time', name='uq_room_time'),
    )
    op.create_index('ix_reservations_start_time', 'reservations', ['start_time'])
    op.create_index('ix_reservations_end_time', 'reservations', ['end_time'])

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', audit_action_enum, nullable=False),
        sa.Column('description', sa.String(length=512)),
        sa.Column('payload', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_index('ix_reservations_end_time', table_name='reservations')
    op.drop_index('ix_reservations_start_time', table_name='reservations')
    op.drop_table('reservations')
    op.drop_table('rooms')
    op.drop_table('users')

    sa.Enum(name='auditaction').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='reservationstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='roomtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
