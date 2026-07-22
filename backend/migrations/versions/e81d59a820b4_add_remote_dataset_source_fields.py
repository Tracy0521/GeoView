"""add remote dataset source fields

Revision ID: e81d59a820b4
Revises: c4f37b0f2a91
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa


revision = 'e81d59a820b4'
down_revision = 'c4f37b0f2a91'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('dataset') as batch_op:
        batch_op.add_column(sa.Column('source_type', sa.String(length=20), nullable=True, server_default='local'))
        batch_op.add_column(sa.Column('source_server', sa.String(length=80), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('remote_path', sa.String(length=500), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('sync_status', sa.String(length=20), nullable=True, server_default='synced'))


def downgrade():
    with op.batch_alter_table('dataset') as batch_op:
        batch_op.drop_column('sync_status')
        batch_op.drop_column('remote_path')
        batch_op.drop_column('source_server')
        batch_op.drop_column('source_type')
