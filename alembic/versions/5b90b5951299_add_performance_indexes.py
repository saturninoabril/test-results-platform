"""Add performance indexes

Revision ID: 5b90b5951299
Revises: 4c76ea741d73
Create Date: 2025-09-14 14:42:45.242207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b90b5951299'
down_revision: Union[str, Sequence[str], None] = '4c76ea741d73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for optimal query performance."""

    # Test Suites indexes - frequently queried by framework, environment, status, and date
    op.create_index(
        'idx_test_suites_framework_started',
        'test_suites',
        ['framework_id', 'started_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_suites_environment_started',
        'test_suites',
        ['environment_id', 'started_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_suites_status_started',
        'test_suites',
        ['status', 'started_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_suites_external_id',
        'test_suites',
        ['external_id'],
        postgresql_using='btree'
    )

    # Test Results indexes - frequently queried by suite, status, tags
    op.create_index(
        'idx_test_results_suite_status',
        'test_results',
        ['suite_id', 'status'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_results_suite_started',
        'test_results',
        ['suite_id', 'started_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_results_external_id',
        'test_results',
        ['external_id'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_results_status_started',
        'test_results',
        ['status', 'started_at'],
        postgresql_using='btree'
    )

    # GIN index for tags array queries
    op.create_index(
        'idx_test_results_tags',
        'test_results',
        ['tags'],
        postgresql_using='gin'
    )

    # Test Artifacts indexes - frequently queried by result and type
    op.create_index(
        'idx_test_artifacts_result_type',
        'test_artifacts',
        ['result_id', 'type'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_artifacts_type_created',
        'test_artifacts',
        ['type', 'created_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_artifacts_size',
        'test_artifacts',
        ['size'],
        postgresql_using='btree'
    )

    # Composite indexes for common query patterns
    op.create_index(
        'idx_test_results_suite_status_duration',
        'test_results',
        ['suite_id', 'status', 'duration_ms'],
        postgresql_using='btree'
    )

    # Partial indexes for performance on specific conditions
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_test_results_failed_recent
        ON test_results (started_at DESC)
        WHERE status = 'failed' AND started_at >= NOW() - INTERVAL '30 days'
    """)

    op.execute("""
        CREATE INDEX CONCURRENTLY idx_test_suites_active
        ON test_suites (started_at DESC, id)
        WHERE status IN ('running', 'pending')
    """)

    # Covering indexes to avoid table lookups for common queries
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_test_results_suite_summary
        ON test_results (suite_id)
        INCLUDE (status, duration_ms, started_at, external_id)
    """)


def downgrade() -> None:
    """Remove performance indexes."""

    # Drop all the indexes we created
    op.drop_index('idx_test_suites_framework_started', 'test_suites')
    op.drop_index('idx_test_suites_environment_started', 'test_suites')
    op.drop_index('idx_test_suites_status_started', 'test_suites')
    op.drop_index('idx_test_suites_external_id', 'test_suites')

    op.drop_index('idx_test_results_suite_status', 'test_results')
    op.drop_index('idx_test_results_suite_started', 'test_results')
    op.drop_index('idx_test_results_external_id', 'test_results')
    op.drop_index('idx_test_results_status_started', 'test_results')
    op.drop_index('idx_test_results_tags', 'test_results')

    op.drop_index('idx_test_artifacts_result_type', 'test_artifacts')
    op.drop_index('idx_test_artifacts_type_created', 'test_artifacts')
    op.drop_index('idx_test_artifacts_size', 'test_artifacts')

    op.drop_index('idx_test_results_suite_status_duration', 'test_results')

    # Drop the manually created indexes
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_test_results_failed_recent")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_test_suites_active")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_test_results_suite_summary")
