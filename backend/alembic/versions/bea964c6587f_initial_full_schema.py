"""initial_full_schema

Revision ID: bea964c6587f
Revises: 
Create Date: 2026-08-19 23:49:13.164573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'bea964c6587f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for the Distributed Job Scheduler.

    Tables (in dependency order):
    1. organizations
    2. users
    3. projects
    4. api_keys
    5. queues
    6. retry_policies
    7. workers
    8. worker_heartbeats
    9. jobs
    10. job_executions
    11. job_logs
    12. dead_letter_entries
    """

    # --- Enum types ---
    job_status_enum = postgresql.ENUM(
        'queued', 'scheduled', 'claimed', 'running',
        'completed', 'failed', 'retrying', 'dead_letter',
        name='job_status',
        create_type=True,
    )
    execution_status_enum = postgresql.ENUM(
        'running', 'completed', 'failed',
        name='execution_status',
        create_type=True,
    )
    worker_status_enum = postgresql.ENUM(
        'online', 'offline', 'draining',
        name='worker_status',
        create_type=True,
    )

    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(320), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 3. projects
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 4. api_keys
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('label', sa.String(255), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. queues
    op.create_table(
        'queues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('concurrency_limit', sa.Integer(), nullable=False, server_default=sa.text('10')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 6. retry_policies
    op.create_table(
        'retry_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('queue_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('queues.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default=sa.text('3')),
        sa.Column('backoff_strategy', sa.String(50), nullable=False, server_default='exponential'),
        sa.Column('backoff_base_seconds', sa.Float(), nullable=False, server_default=sa.text('2.0')),
        sa.Column('backoff_max_seconds', sa.Float(), nullable=False, server_default=sa.text('3600.0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 7. workers
    op.create_table(
        'workers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('status', worker_status_enum, nullable=False, server_default='online'),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 8. worker_heartbeats
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
    )

    # 9. jobs — the central entity
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('queue_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('queues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', job_status_enum, nullable=False, server_default='queued'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('claimed_by_worker_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('depends_on_job_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('dedupe_key', sa.String(255), nullable=True),
        sa.Column('batch_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    # Indexes for the claim query
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_batch_id', 'jobs', ['batch_id'])
    op.create_index('ix_jobs_claimable', 'jobs', ['queue_id', 'status', 'scheduled_at', 'priority'])
    # Unique constraint for idempotent submission
    op.create_unique_constraint('uq_job_queue_dedupe_key', 'jobs', ['queue_id', 'dedupe_key'])

    # 10. job_executions — RESTRICT on job_id deletion (audit trail)
    op.create_table(
        'job_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('jobs.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('workers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', execution_status_enum, nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 11. job_logs
    op.create_table(
        'job_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('job_executions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('level', sa.String(20), nullable=False, server_default='INFO'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    )

    # 12. dead_letter_entries — RESTRICT on job_id deletion (audit trail)
    op.create_table(
        'dead_letter_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('jobs.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('original_payload', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table('dead_letter_entries')
    op.drop_table('job_logs')
    op.drop_table('job_executions')
    op.drop_index('ix_jobs_claimable', table_name='jobs')
    op.drop_index('ix_jobs_batch_id', table_name='jobs')
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('worker_heartbeats')
    op.drop_table('workers')
    op.drop_table('retry_policies')
    op.drop_table('queues')
    op.drop_table('api_keys')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('organizations')

    # Drop enum types
    sa.Enum(name='job_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='execution_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='worker_status').drop(op.get_bind(), checkfirst=True)
