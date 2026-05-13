"""add prompt library tables (F05 단계 1)

Revision ID: d4e5f6a7b8c9
Revises: c3a1f9b2e045
Create Date: 2026-05-11 00:00:00.000000

Creates three tables:
    prompts            — Prompt meta
    prompt_versions    — Immutable body snapshots
    prompt_usages      — StyleVersion-node → PromptVersion links

Spec refs:
    §5.1  prompts table
    §5.2  prompt_versions table (current_version_id FK added via ALTER after both tables exist)
    §5.3  prompt_usages table
    AC-7  All indexes use postgresql_concurrently=True (W5 convention)

Note on circular FK:
    prompts.current_version_id → prompt_versions.id  AND
    prompt_versions.prompt_id  → prompts.id
    To avoid creation-order conflicts the FK on current_version_id is added
    as a deferred ALTER TABLE after both tables exist (spec §5.2).
    SQLAlchemy ORM declares it with use_alter=True so autogenerate would emit
    the same pattern; here we do it manually for clarity and safety.

backfill (style_versions.dag.nodes[] → prompt_usages) is Phase 4, separate migration.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3a1f9b2e045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ prompts
    # current_version_id is nullable TEXT for now; FK added below via ALTER.
    op.create_table(
        "prompts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "node_type",
            sa.Text(),
            sa.CheckConstraint(
                "node_type IN ('text','image','video','composition')",
                name="prompts_node_type_chk",
            ),
            nullable=False,
        ),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('draft','reviewing','approved','deprecated')",
                name="prompts_status_chk",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("current_version_id", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("imported_from", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------ prompt_versions
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "prompt_id",
            sa.Text(),
            sa.ForeignKey("prompts.id", ondelete="CASCADE", name="fk_prompt_versions_prompt_id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "declared_variables",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("model_default", postgresql.JSONB(), nullable=True),
        sa.Column("parent_version_id", sa.Text(), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_id_version"),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["prompt_versions.id"],
            name="fk_prompt_versions_parent_version_id",
        ),
    )

    # ------------------------------------------------------------------ prompt_usages
    op.create_table(
        "prompt_usages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "prompt_id",
            sa.Text(),
            sa.ForeignKey("prompts.id", ondelete="CASCADE", name="fk_prompt_usages_prompt_id"),
            nullable=False,
        ),
        sa.Column(
            "prompt_version_id",
            sa.Text(),
            sa.ForeignKey(
                "prompt_versions.id",
                ondelete="CASCADE",
                name="fk_prompt_usages_prompt_version_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "style_version_id",
            sa.Text(),
            sa.ForeignKey(
                "style_versions.id",
                ondelete="CASCADE",
                name="fk_prompt_usages_style_version_id",
            ),
            nullable=False,
        ),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_run_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "style_version_id", "node_id", name="uq_prompt_usages_style_version_node"
        ),
    )

    # ---- Deferred FK: prompts.current_version_id → prompt_versions.id (spec §5.2)
    # Both tables now exist, safe to add the circular FK.
    op.create_foreign_key(
        "fk_prompts_current_version_id",
        "prompts",
        "prompt_versions",
        ["current_version_id"],
        ["id"],
    )

    # ---- Indexes (all CONCURRENTLY per W5 / AC-7) ----
    # prompts
    op.create_index(
        "idx_prompts_node_type",
        "prompts",
        ["node_type"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    op.create_index(
        "idx_prompts_status",
        "prompts",
        ["status"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    op.create_index(
        "idx_prompts_tags",
        "prompts",
        ["tags"],
        postgresql_using="gin",
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    op.create_index(
        "uq_prompts_imported_from",
        "prompts",
        ["imported_from"],
        unique=True,
        postgresql_where=sa.text("imported_from IS NOT NULL"),
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    # prompt_versions
    op.create_index(
        "idx_prompt_versions_prompt_id",
        "prompt_versions",
        ["prompt_id"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    op.create_index(
        "idx_prompt_versions_parent",
        "prompt_versions",
        ["parent_version_id"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    # prompt_usages
    op.create_index(
        "idx_prompt_usages_prompt_id",
        "prompt_usages",
        ["prompt_id"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    op.create_index(
        "idx_prompt_usages_style_version_id",
        "prompt_usages",
        ["style_version_id"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    # Drop indexes first (CONCURRENTLY requires no active transaction, but
    # standard Alembic downgrade is fine for test/dev environments).
    op.drop_index("idx_prompt_usages_style_version_id", table_name="prompt_usages")
    op.drop_index("idx_prompt_usages_prompt_id", table_name="prompt_usages")
    op.drop_index("idx_prompt_versions_parent", table_name="prompt_versions")
    op.drop_index("idx_prompt_versions_prompt_id", table_name="prompt_versions")
    op.drop_index("uq_prompts_imported_from", table_name="prompts")
    op.drop_index("idx_prompts_tags", table_name="prompts")
    op.drop_index("idx_prompts_status", table_name="prompts")
    op.drop_index("idx_prompts_node_type", table_name="prompts")

    # Drop the deferred FK before dropping prompts (otherwise FK constraint error).
    op.drop_constraint("fk_prompts_current_version_id", "prompts", type_="foreignkey")

    # Drop tables in reverse dependency order.
    op.drop_table("prompt_usages")
    op.drop_table("prompt_versions")
    op.drop_table("prompts")
