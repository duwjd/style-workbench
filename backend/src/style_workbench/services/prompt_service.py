"""PromptService — use-case layer for the Prompt Library (F05).

Implements:
    FR-1  Prompt CRUD
    FR-2  Immutable Versioning
    FR-3  Placeholder Validation
    FR-9  Lifecycle transitions

External SDK imports are strictly forbidden here (spec §8.4 / CLAUDE.md §5.2).
All DB I/O goes through the repository Protocols defined in domain/prompt/repo.py.
Transaction boundaries are managed by the caller (FastAPI dependency injects
the session; flush/commit happens outside this class).
"""

from __future__ import annotations

import hashlib

import structlog

from style_workbench.core.errors import (
    InvalidPromptStatusTransitionError,
    MissingDeclaredVariableError,
    PromptAbComparisonNotFoundError,
    PromptAbSameVersionError,
    PromptDeprecatedError,
    PromptNotFoundError,
    PromptVersionNotFoundError,
    StyleVersionHasNoPromptNodeError,
)
from style_workbench.core.ids import new_ulid
from style_workbench.domain.prompt.entity import (
    _STATUS_TRANSITIONS,
    DeclaredVariable,
    ModelDefault,
    NodeType,
    Prompt,
    PromptAbComparison,
    PromptFilters,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.domain.prompt.repo import (
    PromptAbComparisonRepo,
    PromptRepo,
    PromptUsageRepo,
    PromptVersionRepo,
)
from style_workbench.domain.prompt.validation import (
    PromptValidationError,
    validate_placeholders,
)

logger = structlog.get_logger(__name__)


class PromptService:
    """Orchestrates Prompt Library use-cases.

    All write operations flush via the injected repositories which share the
    same AsyncSession.  The FastAPI route handler is responsible for committing
    (or rolling back on exception) the session after the service call returns.
    """

    def __init__(
        self,
        prompt_repo: PromptRepo,
        version_repo: PromptVersionRepo,
        usage_repo: PromptUsageRepo,
        ab_repo: PromptAbComparisonRepo | None = None,
    ) -> None:
        self._prompt_repo = prompt_repo
        self._version_repo = version_repo
        self._usage_repo = usage_repo
        self._ab_repo = ab_repo

    # ------------------------------------------------------------------
    # FR-1: Prompt CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        name: str,
        node_type: NodeType,
        body: str,
        declared_variables: list[DeclaredVariable],
        owner: str | None = None,
        tags: list[str] | None = None,
        model_default: ModelDefault | None = None,
        change_note: str | None = None,
        created_by: str | None = None,
        imported_from: str | None = None,
        initial_status: PromptStatus = PromptStatus.DRAFT,
    ) -> Prompt:
        """Create a new Prompt with status=draft (or initial_status) and version=1.

        Validates that every placeholder in *body* is listed in *declared_variables*
        (FR-3) before persisting.  Raises MissingDeclaredVariableError on violation.
        """
        _validate_body_placeholders(body, declared_variables)

        prompt_id = new_ulid()
        version_id = new_ulid()

        prompt = Prompt(
            id=prompt_id,
            name=name,
            node_type=node_type,
            status=initial_status,
            owner=owner,
            tags=tags or [],
            imported_from=imported_from,
        )
        saved_prompt = await self._prompt_repo.save(prompt)

        version = PromptVersion(
            id=version_id,
            prompt_id=prompt_id,
            version=1,
            body=body,
            declared_variables=declared_variables,
            model_default=model_default,
            parent_version_id=None,
            change_note=change_note,
            created_by=created_by,
        )
        saved_version = await self._version_repo.save(version)

        # Point current_version_id to the newly created version.
        saved_prompt.current_version_id = saved_version.id
        saved_prompt.current_version = saved_version
        updated = await self._prompt_repo.update(saved_prompt)
        updated.current_version = saved_version

        logger.info(
            "prompt_created",
            prompt_id=prompt_id,
            node_type=str(node_type),
            body_hash=_body_hash(body),
        )
        return updated

    async def get(self, prompt_id: str) -> Prompt:
        """Return the Prompt with its current_version loaded.

        Raises PromptNotFoundError if not found.
        """
        prompt = await self._prompt_repo.get_with_version(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")
        return prompt

    async def update_meta(
        self,
        prompt_id: str,
        *,
        name: str | None = None,
        tags: list[str] | None = None,
        status: PromptStatus | None = None,
        owner: str | None = None,
    ) -> Prompt:
        """Update in-place metadata fields (name, tags, status, owner).

        Body changes must go through create_version().
        Validates lifecycle transition if status is provided.
        """
        prompt = await self._prompt_repo.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

        if name is not None:
            prompt.name = name
        if tags is not None:
            prompt.tags = tags
        if owner is not None:
            prompt.owner = owner
        if status is not None:
            _validate_status_transition(prompt.status, status)
            prompt.status = status

        updated = await self._prompt_repo.update(prompt)
        logger.info("prompt_meta_updated", prompt_id=prompt_id)
        return updated

    async def list_prompts(self, filters: PromptFilters) -> list[Prompt]:
        """Return a page of Prompts matching filters (spec §6.1)."""
        return await self._prompt_repo.list(filters)

    async def find_by_imported_from(self, imported_from: str) -> Prompt | None:
        """Return the Prompt with the given imported_from path, or None.

        Used by the CLI import tool for idempotency checks (spec §4 FR-7).
        """
        return await self._prompt_repo.find_by_imported_from(imported_from)

    # ------------------------------------------------------------------
    # FR-2: Immutable Versioning
    # ------------------------------------------------------------------

    async def create_version(
        self,
        prompt_id: str,
        body: str,
        declared_variables: list[DeclaredVariable],
        change_note: str | None = None,
        model_default: ModelDefault | None = None,
        created_by: str | None = None,
    ) -> PromptVersion:
        """Append a new immutable version for the given prompt.

        Does NOT automatically promote — call promote_version() separately.
        Validates body placeholders before persisting (FR-3).
        """
        prompt = await self._prompt_repo.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

        _validate_body_placeholders(body, declared_variables)

        next_ver = await self._version_repo.next_version_number(prompt_id)

        # parent_version_id = current version at time of branching (F02 lineage)
        parent_version_id = prompt.current_version_id

        version = PromptVersion(
            id=new_ulid(),
            prompt_id=prompt_id,
            version=next_ver,
            body=body,
            declared_variables=declared_variables,
            model_default=model_default,
            parent_version_id=parent_version_id,
            change_note=change_note,
            created_by=created_by,
        )
        saved = await self._version_repo.save(version)
        logger.info(
            "prompt_version_created",
            prompt_id=prompt_id,
            version=next_ver,
            body_hash=_body_hash(body),
        )
        return saved

    async def list_versions(
        self,
        prompt_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Return paginated PromptVersions for *prompt_id*, ordered version DESC.

        Raises PromptNotFoundError if the prompt does not exist.
        Returns (items, total).
        """
        prompt = await self._prompt_repo.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

        return await self._version_repo.list_by_prompt(prompt_id, limit=limit, offset=offset)

    async def get_version(self, prompt_id: str, version: int) -> PromptVersion:
        """Return a specific PromptVersion by prompt_id and version number.

        Raises:
            PromptNotFoundError: If the parent prompt does not exist.
            PromptVersionNotFoundError: If the version number does not exist for this prompt.
        """
        prompt = await self._prompt_repo.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

        pv = await self._version_repo.get_by_prompt_and_number(prompt_id, version)
        if pv is None:
            raise PromptVersionNotFoundError(
                f"PromptVersion v{version} not found for prompt '{prompt_id}'"
            )
        return pv

    async def promote_version(self, prompt_id: str, version_id: str) -> Prompt:
        """Set the given version as current_version_id for the prompt.

        Validates:
        - Prompt exists.
        - Version exists and belongs to this prompt.
        - Prompt status allows promote (deprecated prompts cannot be promoted).

        Uses a fetch-then-update pattern; the caller's session must hold
        the transaction open for atomicity (spec §8.3 SELECT FOR UPDATE note).
        """
        prompt = await self._prompt_repo.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

        if prompt.status == PromptStatus.DEPRECATED:
            raise PromptDeprecatedError(
                f"Cannot promote version on deprecated prompt '{prompt_id}'"
            )

        version = await self._version_repo.get(version_id)
        if version is None or version.prompt_id != prompt_id:
            raise PromptVersionNotFoundError(
                f"PromptVersion '{version_id}' not found for prompt '{prompt_id}'"
            )

        prompt.current_version_id = version_id
        updated = await self._prompt_repo.update(prompt)
        updated.current_version = version
        logger.info("prompt_version_promoted", prompt_id=prompt_id, version_id=version_id)
        return updated

    # ------------------------------------------------------------------
    # FR-6: Usage tracking helpers (called by RunService post-evaluation)
    # ------------------------------------------------------------------

    async def record_usage(
        self,
        prompt_id: str,
        prompt_version_id: str,
        style_version_id: str,
        node_id: str,
        pinned: bool = False,
    ) -> PromptUsage:
        """Create a PromptUsage entry linking a Style node to a PromptVersion."""
        usage = PromptUsage(
            id=new_ulid(),
            prompt_id=prompt_id,
            prompt_version_id=prompt_version_id,
            style_version_id=style_version_id,
            node_id=node_id,
            pinned=pinned,
        )
        return await self._usage_repo.save(usage)

    async def update_usage_score(self, usage_id: str, score: float) -> PromptUsage:
        """Update last_run_score for a PromptUsage after evaluation (FR-6)."""
        usage = await self._usage_repo.update_run_score(usage_id, score)
        if usage is None:
            raise PromptNotFoundError(f"PromptUsage '{usage_id}' not found")
        return usage

    async def list_usages(
        self, prompt_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[PromptUsage], int]:
        """Return (usages, total_count) for a given prompt."""
        usages = await self._usage_repo.list_for_prompt(prompt_id, limit=limit, offset=offset)
        total = await self._usage_repo.count_for_prompt(prompt_id)
        return usages, total

    # ------------------------------------------------------------------
    # FR-8: A/B Comparison (단계 5)
    # ------------------------------------------------------------------

    async def trigger_ab(
        self,
        prompt_id: str,
        from_version_id: str,
        to_version_id: str,
        style_version_id: str,
        user_input: dict[str, str],
        run_service: object,
    ) -> PromptAbComparison:
        """Trigger an A/B comparison between two PromptVersions.

        Validates:
          - Prompt exists.
          - from_version_id and to_version_id are different (same version → 422).
          - Both versions exist and belong to this prompt.
          - The style_version has at least one node referencing this prompt.

        Then runs both versions serially (F03 미구현 — 직렬 실행 per spec §4 FR-8).
        Persists a PromptAbComparison record.

        Returns the PromptAbComparison with from_run_id and to_run_id populated.

        External SDK imports: NONE — RunService encapsulates all model calls.
        """
        from datetime import UTC, datetime

        from style_workbench.services.run_service import RunService

        assert isinstance(run_service, RunService), "run_service must be a RunService instance"

        if from_version_id == to_version_id:
            raise PromptAbSameVersionError(
                f"from_version_id and to_version_id are the same: '{from_version_id}'. "
                "A/B comparison requires two distinct versions."
            )

        # Verify prompt exists
        prompt = await self._prompt_repo.get(prompt_id)
        if prompt is None:
            raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

        # Verify both versions belong to this prompt
        from_version = await self._version_repo.get(from_version_id)
        if from_version is None or from_version.prompt_id != prompt_id:
            raise PromptVersionNotFoundError(
                f"PromptVersion '{from_version_id}' not found for prompt '{prompt_id}'"
            )
        to_version = await self._version_repo.get(to_version_id)
        if to_version is None or to_version.prompt_id != prompt_id:
            raise PromptVersionNotFoundError(
                f"PromptVersion '{to_version_id}' not found for prompt '{prompt_id}'"
            )

        # Verify the style_version has a node referencing this prompt
        node_id = await _find_prompt_node_in_style(
            prompt_id=prompt_id,
            style_version_id=style_version_id,
            usage_repo=self._usage_repo,
        )
        if node_id is None:
            raise StyleVersionHasNoPromptNodeError(
                f"StyleVersion '{style_version_id}' has no node referencing prompt '{prompt_id}'. "
                "Use a style_version_id where this prompt is actually linked."
            )

        ab_id = new_ulid()
        now = datetime.now(UTC)
        ab = PromptAbComparison(
            id=ab_id,
            prompt_id=prompt_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            style_version_id=style_version_id,
            user_input=dict(user_input),
            status="running",
            created_at=now,
            started_at=now,
        )

        assert self._ab_repo is not None, "ab_repo required for trigger_ab()"
        saved_ab = await self._ab_repo.save(ab)

        logger.info(
            "ab_comparison_started",
            ab_id=ab_id,
            prompt_id=prompt_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            style_version_id=style_version_id,
        )

        # --- Serial execution: from_version first, then to_version ---
        # F03 미구현 → 직렬 실행 (spec §4 FR-8).
        # Each version is patched into the style DAG's node before executing.

        from_run_id: str | None = None
        to_run_id: str | None = None

        try:
            from_run = await run_service.execute(
                style_version_id=style_version_id,
                user_input=dict(user_input),
                prompt_override={node_id: from_version.body},
            )
            from_run_id = from_run.id

            to_run = await run_service.execute(
                style_version_id=style_version_id,
                user_input=dict(user_input),
                prompt_override={node_id: to_version.body},
            )
            to_run_id = to_run.id

            saved_ab.from_run_id = from_run_id
            saved_ab.to_run_id = to_run_id
            saved_ab.status = "done"
            saved_ab.finished_at = datetime.now(UTC)
        except Exception:
            saved_ab.from_run_id = from_run_id
            saved_ab.to_run_id = to_run_id
            saved_ab.status = "failed"
            saved_ab.finished_at = datetime.now(UTC)
            logger.warning(
                "ab_comparison_failed",
                ab_id=ab_id,
                prompt_id=prompt_id,
                from_run_id=from_run_id,
                to_run_id=to_run_id,
            )
            raise

        finally:
            # Always persist final state of the AB record (even on failure)
            try:
                saved_ab = await self._ab_repo.update(saved_ab)
            except Exception as update_exc:
                logger.error(
                    "ab_comparison_update_failed",
                    ab_id=ab_id,
                    error=str(update_exc),
                )

        logger.info(
            "ab_comparison_done",
            ab_id=ab_id,
            from_run_id=from_run_id,
            to_run_id=to_run_id,
        )
        return saved_ab

    async def get_ab(self, ab_id: str) -> PromptAbComparison:
        """Return an A/B comparison record by id."""
        assert self._ab_repo is not None, "ab_repo required for get_ab()"
        ab = await self._ab_repo.get(ab_id)
        if ab is None:
            raise PromptAbComparisonNotFoundError(f"PromptAbComparison '{ab_id}' not found")
        return ab


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_body_placeholders(body: str, declared_variables: list[DeclaredVariable]) -> None:
    """Wrap domain validation error into the service-layer error hierarchy.

    PromptValidationError (domain) is re-raised as MissingDeclaredVariableError
    (core/errors.py) so the API exception handler maps it to HTTP 422 cleanly.
    """
    try:
        validate_placeholders(body, declared_variables)
    except PromptValidationError as exc:
        raise MissingDeclaredVariableError(str(exc)) from exc


def _validate_status_transition(current: PromptStatus, target: PromptStatus) -> None:
    allowed = _STATUS_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidPromptStatusTransitionError(
            f"Cannot transition prompt status from '{current}' to '{target}'. "
            f"Allowed: {sorted(str(s) for s in allowed) or 'none (terminal state)'}"
        )


def _body_hash(body: str) -> str:
    """Return a short SHA-256 hex digest of the body for structured logging.

    Per CLAUDE.md §9: prompt body must not appear in logs — only a hash.
    """
    return hashlib.sha256(body.encode()).hexdigest()[:16]


async def _find_prompt_node_in_style(
    prompt_id: str,
    style_version_id: str,
    usage_repo: PromptUsageRepo,
) -> str | None:
    """Return the first node_id in the style_version that references *prompt_id*.

    Uses the prompt_usages table (spec §5.3) which records the (style_version_id,
    node_id) → prompt_id mapping.  This avoids parsing the raw DAG JSONB and
    keeps the lookup within the domain repository layer.

    Returns None if no node in the style_version references this prompt.
    """
    # list_for_prompt returns usages for the prompt ordered by created_at DESC.
    # We filter by style_version_id in Python since the list is typically short (≤20).
    usages = await usage_repo.list_for_prompt(prompt_id, limit=100, offset=0)
    for usage in usages:
        if usage.style_version_id == style_version_id:
            return usage.node_id
    return None
