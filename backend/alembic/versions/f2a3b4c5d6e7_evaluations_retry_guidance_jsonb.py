"""evaluations.retry_guidance JSONB + failed_dimensions (F01 단계 2)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-11 00:00:00.000000

Changes (§13 단계 2 / §5.2):
    1. evaluations.retry_guidance  TEXT → JSONB (nullable).
       기존 plain-text 행은 {"instruction": <original_text>} 형태로 안전 변환.
       dev 환경에서는 데이터가 없거나 text 형태이므로 USING 절로 안전 처리.
    2. evaluations.failed_dimensions  JSONB NOT NULL DEFAULT '[]'  신규 컬럼.

Downgrade:
    failed_dimensions 컬럼 삭제.
    retry_guidance JSONB → TEXT (->>'instruction' 추출, NULL 보존).

Notes:
    - 두 변경 모두 nullable 또는 default 있음 → 기존 row 0건 영향.
    - CONCURRENTLY 인덱스 없음 (기존 ix_evaluations_node_execution_id 유지).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ retry_guidance: TEXT → JSONB
    # USING 절: NULL이면 NULL, 기존 text가 이미 유효한 JSON이면 ::jsonb,
    # plain string이면 {"instruction": <text>} 객체로 wrap.
    # dev 환경(빈 테이블)에서도 안전하게 동작한다.
    op.alter_column(
        "evaluations",
        "retry_guidance",
        type_=postgresql.JSONB(),
        postgresql_using=(
            "CASE "
            "  WHEN retry_guidance IS NULL THEN NULL "
            "  ELSE jsonb_build_object('instruction', retry_guidance) "
            "END"
        ),
        nullable=True,
        existing_nullable=True,
    )

    # ------------------------------------------------------------------ failed_dimensions: 신규 JSONB 컬럼
    op.add_column(
        "evaluations",
        sa.Column(
            "failed_dimensions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    # failed_dimensions 제거
    op.drop_column("evaluations", "failed_dimensions")

    # retry_guidance: JSONB → TEXT (instruction 키 값 추출, NULL 보존)
    op.alter_column(
        "evaluations",
        "retry_guidance",
        type_=sa.Text(),
        postgresql_using=(
            "CASE "
            "  WHEN retry_guidance IS NULL THEN NULL "
            "  ELSE retry_guidance->>'instruction' "
            "END"
        ),
        nullable=True,
        existing_nullable=True,
    )
