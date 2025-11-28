"""add room booking window

Revision ID: 11ce4f7af00e
Revises: 0001_initial
Create Date: 2025-11-08 14:41:47.958573

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '11ce4f7af00e'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rooms', sa.Column('booking_start', sa.Time(), nullable=True))
    op.add_column('rooms', sa.Column('booking_end', sa.Time(), nullable=True))


def downgrade():
    op.drop_column('rooms', 'booking_end')
    op.drop_column('rooms', 'booking_start')
