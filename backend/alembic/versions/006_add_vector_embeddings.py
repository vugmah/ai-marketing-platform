"""Add vector_embeddings table

Revision ID: 006
Revises: 005
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005_governance_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the vector_embeddings table for pgvector (PostgreSQL only)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # Skip on MySQL - pgvector/ARRAY is PostgreSQL-only

    # Try to create pgvector extension
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        pass  # pgvector may not be installed, ARRAY will be used as fallback

    op.create_table(
        "vector_embeddings",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column(
            "embedding",
            sa.ARRAY(sa.Float),
            nullable=False,
            comment="Vector embedding as float array (pgvector compatible)",
        ),
        sa.Column(
            "entity_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.Integer,
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Integer,
            sa.ForeignKey(
                "companies.id",
                ondelete="CASCADE",
                name="fk_vector_embeddings_company_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.Integer,
            sa.ForeignKey(
                "branches.id",
                ondelete="SET NULL",
                name="fk_vector_embeddings_branch_id",
            ),
            nullable=True,
        ),
        sa.Column(
            "content",
            sa.Text,
            nullable=False,
            default="",
        ),
        sa.Column(
            "metadata",
            sa.JSON,
            nullable=True,
            default=dict,
            comment="Arbitrary metadata dict (JSON)",
        ),
        sa.Column(
            "created_at",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Unix timestamp for TTL support",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vector_embeddings"),
        sa.UniqueConstraint("id", name="uq_vector_embeddings_id"),
        schema=None,
    )

    # Create indexes
    op.create_index(
        "ix_vector_embeddings_entity_type",
        "vector_embeddings",
        ["entity_type"],
        schema=None,
    )
    op.create_index(
        "ix_vector_embeddings_entity_id",
        "vector_embeddings",
        ["entity_id"],
        schema=None,
    )
    op.create_index(
        "ix_vector_embeddings_company_id",
        "vector_embeddings",
        ["company_id"],
        schema=None,
    )
    op.create_index(
        "ix_vector_embeddings_branch_id",
        "vector_embeddings",
        ["branch_id"],
        schema=None,
    )
    op.create_index(
        "ix_vector_embeddings_created_at",
        "vector_embeddings",
        ["created_at"],
        schema=None,
    )

    # Composite index for common queries
    op.create_index(
        "ix_vector_embeddings_company_entity",
        "vector_embeddings",
        ["company_id", "entity_type", "entity_id"],
        schema=None,
    )

    # GIN index on metadata for JSON filtering
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_vector_embeddings_metadata
        ON vector_embeddings
        USING GIN (metadata jsonb_path_ops)
        """
    )


def downgrade() -> None:
    """Drop the vector_embeddings table (PostgreSQL only)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # Skip on MySQL - table was never created
    op.drop_index(
        "ix_vector_embeddings_metadata",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_index(
        "ix_vector_embeddings_company_entity",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_index(
        "ix_vector_embeddings_created_at",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_index(
        "ix_vector_embeddings_branch_id",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_index(
        "ix_vector_embeddings_company_id",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_index(
        "ix_vector_embeddings_entity_id",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_index(
        "ix_vector_embeddings_entity_type",
        table_name="vector_embeddings",
        schema=None,
    )
    op.drop_table("vector_embeddings", schema=None)
