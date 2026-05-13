"""backfill prompt_usages from inline style_versions.dag.nodes[].prompt_template

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-05-11 00:00:00.000000

spec §5.4 단계 2 — online backfill migration.

For every style_versions row, each node that has a non-empty prompt_template
and does NOT already have a prompt_id set is converted into:

    1. prompts row         — status='draft', imported_from='inline:<style_id>:<node_id>'
    2. prompt_versions row — version=1, body=prompt_template,
                             declared_variables extracted from body
    3. prompt_usages row   — pinned=True (preserves existing behaviour;
                             the node stays locked to this exact version)
    4. node's JSONB fields — prompt_id + prompt_version_id set.
                             prompt_template left intact (rollback safety,
                             spec §5.4 단계 3 deprecation is a separate migration)

Idempotency:
    imported_from='inline:<style_id>:<node_id>' is unique-indexed.
    If the row already exists (prior partial run), this node is skipped.

Downgrade:
    Deletes all prompt_usages / prompt_versions / prompts rows where
    imported_from starts with 'inline:'.
    Restores nodes' prompt_id / prompt_version_id to NULL.

Performance notes:
    - Iterates rows in Python (op.get_bind() + Core queries).
    - Safe for 1–10k style_versions; for larger datasets batch-chunk or
      run as an offline script.
    - Because it is a data migration, --sql mode shows no DDL output.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Helpers (duplicated here to avoid importing application code from migrations)
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")


def _extract_placeholders(body: str) -> list[str]:
    return sorted(set(_PLACEHOLDER_PATTERN.findall(body)))


def _new_ulid() -> str:
    """Generate a new ULID string without importing the application package."""
    from ulid import ULID  # noqa: PLC0415

    return str(ULID())


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    conn = op.get_bind()

    style_versions_tbl = sa.table(
        "style_versions",
        sa.column("id", sa.Text),
        sa.column("style_id", sa.Text),
        sa.column("dag", sa.JSON),
    )
    prompts_tbl = sa.table(
        "prompts",
        sa.column("id", sa.Text),
        sa.column("name", sa.Text),
        sa.column("node_type", sa.Text),
        sa.column("owner", sa.Text),
        sa.column("status", sa.Text),
        sa.column("current_version_id", sa.Text),
        sa.column("tags", sa.ARRAY(sa.Text)),
        sa.column("imported_from", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    prompt_versions_tbl = sa.table(
        "prompt_versions",
        sa.column("id", sa.Text),
        sa.column("prompt_id", sa.Text),
        sa.column("version", sa.Integer),
        sa.column("body", sa.Text),
        sa.column("declared_variables", sa.JSON),
        sa.column("model_default", sa.JSON),
        sa.column("parent_version_id", sa.Text),
        sa.column("change_note", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.Text),
    )
    prompt_usages_tbl = sa.table(
        "prompt_usages",
        sa.column("id", sa.Text),
        sa.column("prompt_id", sa.Text),
        sa.column("prompt_version_id", sa.Text),
        sa.column("style_version_id", sa.Text),
        sa.column("node_id", sa.Text),
        sa.column("pinned", sa.Boolean),
        sa.column("last_run_score", sa.Numeric(4, 3)),
        sa.column("last_run_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    # Fetch all style_versions
    rows = conn.execute(sa.select(style_versions_tbl)).fetchall()

    now = _now_utc()
    n_migrated = 0
    n_skipped = 0

    for row in rows:
        sv_id: str = row.id
        style_id: str = row.style_id
        dag: dict[str, Any] = row.dag if isinstance(row.dag, dict) else {}

        nodes: list[dict[str, Any]] = dag.get("nodes", [])
        dag_changed = False

        for node in nodes:
            node_id: str = node.get("id", "")
            if not node_id:
                continue

            # Skip nodes that already have prompt_id set (idempotent on partial runs)
            if node.get("prompt_id"):
                n_skipped += 1
                continue

            prompt_template: str = node.get("prompt_template") or ""
            if not prompt_template.strip():
                # No inline body — nothing to migrate for this node
                continue

            imported_from = f"inline:{style_id}:{node_id}"

            # Idempotency: check if prompt already created for this node
            existing = conn.execute(
                sa.select(prompts_tbl.c.id, prompts_tbl.c.current_version_id).where(
                    prompts_tbl.c.imported_from == imported_from
                )
            ).fetchone()

            if existing is not None:
                # Prompt already exists from a previous partial run.
                # Still patch the JSONB so the node is linked.
                prompt_id = existing.id
                version_id = existing.current_version_id
                if prompt_id and version_id:
                    node["prompt_id"] = prompt_id
                    node["prompt_version_id"] = version_id
                    node["prompt_pinned"] = True
                    dag_changed = True
                n_skipped += 1
                continue

            # Derive node_type from the style node type string
            style_node_type: str = node.get("type", "")
            node_type = _map_style_node_type(style_node_type)

            # Extract declared_variables from body
            placeholder_names = _extract_placeholders(prompt_template)
            declared_vars = [
                {"name": name, "role": "unknown", "required": True} for name in placeholder_names
            ]

            # Derive a human-readable name
            prompt_name = f"[inline] {style_id}:{node_id}"

            prompt_id = _new_ulid()
            version_id = _new_ulid()
            usage_id = _new_ulid()

            # 1. Insert prompts row
            conn.execute(
                prompts_tbl.insert().values(
                    id=prompt_id,
                    name=prompt_name,
                    node_type=node_type,
                    owner=None,
                    status="draft",
                    current_version_id=version_id,
                    tags=[node_type],
                    imported_from=imported_from,
                    created_at=now,
                    updated_at=now,
                )
            )

            # 2. Insert prompt_versions row
            conn.execute(
                prompt_versions_tbl.insert().values(
                    id=version_id,
                    prompt_id=prompt_id,
                    version=1,
                    body=prompt_template,
                    declared_variables=json.dumps(declared_vars),
                    model_default=None,
                    parent_version_id=None,
                    change_note="backfill from inline prompt_template",
                    created_at=now,
                    created_by="migration:backfill_prompt_usages",
                )
            )

            # 3. Insert prompt_usages row (pinned=True — preserve existing behaviour)
            conn.execute(
                prompt_usages_tbl.insert().values(
                    id=usage_id,
                    prompt_id=prompt_id,
                    prompt_version_id=version_id,
                    style_version_id=sv_id,
                    node_id=node_id,
                    pinned=True,
                    last_run_score=None,
                    last_run_at=None,
                    created_at=now,
                )
            )

            # 4. Patch node JSONB fields
            node["prompt_id"] = prompt_id
            node["prompt_version_id"] = version_id
            node["prompt_pinned"] = True
            # prompt_template left intact (spec §5.4 단계 3 deprecation is separate)
            dag_changed = True
            n_migrated += 1

        # Persist DAG changes back to style_versions
        if dag_changed:
            updated_dag = dict(dag)
            updated_dag["nodes"] = nodes
            conn.execute(
                sa.update(style_versions_tbl)
                .where(style_versions_tbl.c.id == sv_id)
                .values(dag=json.dumps(updated_dag))
            )

    # Structured summary (goes to alembic output, not application logs)
    print(f"backfill_prompt_usages: migrated={n_migrated}, skipped={n_skipped}")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    conn = op.get_bind()

    # 1. Fetch all prompts that were created by this backfill
    backfill_rows = conn.execute(
        sa.text("SELECT id, imported_from FROM prompts WHERE imported_from LIKE 'inline:%'")
    ).fetchall()

    if not backfill_rows:
        return

    backfill_prompt_ids = [row.id for row in backfill_rows]
    imported_from_by_id: dict[str, str] = {row.id: row.imported_from for row in backfill_rows}

    # 2. For each prompt, restore the corresponding style_version node's JSONB fields.
    for prompt_id, imported_from in imported_from_by_id.items():
        # imported_from format: "inline:<style_id>:<node_id>"
        parts = imported_from.split(":", 2)
        if len(parts) != 3:
            continue
        _, style_id, node_id = parts

        # Find the style_version for this style_id + node_id combination.
        # A node_id is unique within a style_version; we look for it in all versions.
        sv_rows = conn.execute(
            sa.text("SELECT id, dag FROM style_versions WHERE style_id = :sid"),
            {"sid": style_id},
        ).fetchall()

        for sv_row in sv_rows:
            dag: dict[str, Any] = sv_row.dag if isinstance(sv_row.dag, dict) else {}
            nodes: list[dict[str, Any]] = dag.get("nodes", [])
            changed = False
            for node in nodes:
                if node.get("id") == node_id and node.get("prompt_id") == prompt_id:
                    node.pop("prompt_id", None)
                    node.pop("prompt_version_id", None)
                    node.pop("prompt_pinned", None)
                    changed = True
            if changed:
                updated_dag = dict(dag)
                updated_dag["nodes"] = nodes
                conn.execute(
                    sa.text("UPDATE style_versions SET dag = :dag WHERE id = :id"),
                    {"dag": json.dumps(updated_dag), "id": sv_row.id},
                )

    # 3. Delete prompt_usages, prompt_versions, prompts in correct FK order.
    # Use individual parameterised deletes to avoid SQL injection via format strings.
    if backfill_prompt_ids:
        for pid in backfill_prompt_ids:
            conn.execute(sa.text("DELETE FROM prompt_usages WHERE prompt_id = :pid"), {"pid": pid})
        for pid in backfill_prompt_ids:
            conn.execute(
                sa.text("DELETE FROM prompt_versions WHERE prompt_id = :pid"), {"pid": pid}
            )
        # Must break FK cycle: current_version_id → prompt_versions before deleting prompts
        for pid in backfill_prompt_ids:
            conn.execute(
                sa.text("UPDATE prompts SET current_version_id = NULL WHERE id = :pid"),
                {"pid": pid},
            )
        for pid in backfill_prompt_ids:
            conn.execute(sa.text("DELETE FROM prompts WHERE id = :pid"), {"pid": pid})

    print(f"backfill_prompt_usages downgrade: removed {len(backfill_prompt_ids)} prompts")


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------


def _map_style_node_type(style_node_type: str) -> str:
    """Map style NodeType string to Prompt Library node_type string.

    style DAG node type vocabulary:
        "text_generation"  → "text"
        "image_generation" → "image"
        "video_generation" → "video"
        "composition"      → "composition"
        (unknown)          → "text"  (safe default)
    """
    _MAP = {
        "text_generation": "text",
        "image_generation": "image",
        "video_generation": "video",
        "composition": "composition",
    }
    return _MAP.get(style_node_type, "text")
