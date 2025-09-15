"""Add performance indexes

Revision ID: 5b90b5951299
Revises: 4c76ea741d73
Create Date: 2025-09-14 14:42:45.242207

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5b90b5951299'
down_revision: str | Sequence[str] | None = '4c76ea741d73'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add performance indexes for optimal query performance."""

    # Test Suites indexes - no new indexes needed (external_id doesn't exist in test_suites)

    # Test Results indexes - only add new ones not in initial migration
    op.create_index(
        'idx_test_results_suite_created',
        'test_results',
        ['suite_id', 'created_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_results_status_created',
        'test_results',
        ['status', 'created_at'],
        postgresql_using='btree'
    )

    # Test Artifacts indexes - fix column names and add new ones
    op.create_index(
        'idx_test_artifacts_type_created',
        'test_artifacts',
        ['artifact_type', 'created_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_test_artifacts_size',
        'test_artifacts',
        ['file_size'],
        postgresql_using='btree'
    )

    # Composite indexes for common query patterns
    op.create_index(
        'idx_test_results_suite_status_duration',
        'test_results',
        ['suite_id', 'status', 'duration_ms'],
        postgresql_using='btree'
    )

    # Additional basic indexes for performance
    pass  # All needed indexes already exist in initial migration


def downgrade() -> None:
    """Remove performance indexes."""

    # Drop only the indexes we created in this migration
    op.drop_index('idx_test_results_suite_created', 'test_results')
    op.drop_index('idx_test_results_status_created', 'test_results')
    op.drop_index('idx_test_artifacts_type_created', 'test_artifacts')
    op.drop_index('idx_test_artifacts_size', 'test_artifacts')
    op.drop_index('idx_test_results_suite_status_duration', 'test_results')
