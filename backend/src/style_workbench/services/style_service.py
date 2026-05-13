from __future__ import annotations

from typing import Any

from style_workbench.core.errors import StyleNotFoundError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.style.entity import DAG, Style
from style_workbench.domain.style.validation import validate_dag
from style_workbench.infra.repositories.style_repo import (
    StyleRecord,
    StyleRepository,
    StyleVersionRecord,
)


class StyleService:
    def __init__(self, repo: StyleRepository) -> None:
        self._repo = repo

    async def create(
        self,
        name: str,
        concept: str,
        vertical: str,
        tags: list[str],
        dag: DAG,
        created_by: str | None = None,
    ) -> StyleRecord:
        validate_dag(dag)
        style = Style(
            id=new_ulid(),
            name=name,
            concept=concept,
            vertical=vertical,
            tags=tags,
            status="draft",
            current_version=1,
            dag=dag,
            created_by=created_by,
        )
        return await self._repo.save(style)

    async def get(self, style_id: str) -> StyleRecord:
        record = await self._repo.get(style_id)
        if record is None:
            raise StyleNotFoundError(f"Style '{style_id}' not found")
        return record

    async def list(self, limit: int = 50, offset: int = 0) -> list[StyleRecord]:
        return await self._repo.list(limit=limit, offset=offset)

    async def update_status(self, style_id: str, status: str) -> StyleRecord:
        record = await self._repo.update_status(style_id, status)
        if record is None:
            raise StyleNotFoundError(f"Style '{style_id}' not found")
        return record

    async def save_dag(
        self,
        style_id: str,
        dag: DAG,
        brief: dict[str, Any] | None = None,
    ) -> StyleVersionRecord:
        """Validate the DAG and create a new version for the given style.

        Steps:
        1. Verify the style exists (StyleNotFoundError → 404 if not).
        2. Validate DAG structure (DagValidationError → 422 if invalid).
        3. Insert new style_versions row (version = current_version + 1).
        4. Update styles.current_version.
        All steps run inside the session's transaction boundary managed by the caller.
        """
        existing = await self._repo.get(style_id)
        if existing is None:
            raise StyleNotFoundError(f"Style '{style_id}' not found")

        validate_dag(dag)

        return await self._repo.create_version(style_id, dag, brief=brief)
