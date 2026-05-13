"""Repository Protocols for the Prompt Library (spec §4 FR-1, FR-2, FR-6).

Convention (backend/CLAUDE.md §5.3):
  - Protocol (interface) lives here in domain/prompt/repo.py.
  - SQLAlchemy implementation lives in infra/repositories/prompt_repo.py.
  - All method signatures use domain entities (Prompt, PromptVersion, PromptUsage).
  - ORM models must NOT be referenced here.

Domain must not import from infra/services/api.
"""

from __future__ import annotations

from typing import Protocol

from style_workbench.domain.prompt.entity import (
    Prompt,
    PromptAbComparison,
    PromptFilters,
    PromptUsage,
    PromptVersion,
)


class PromptRepo(Protocol):
    """CRUD + list operations for the Prompt aggregate root."""

    async def save(self, prompt: Prompt) -> Prompt:
        """Insert a new Prompt row and return the saved entity (with DB-assigned timestamps)."""
        ...

    async def get(self, prompt_id: str) -> Prompt | None:
        """Return the Prompt by id, or None if not found.

        Does NOT eagerly load current_version — use get_with_version for that.
        """
        ...

    async def get_with_version(self, prompt_id: str) -> Prompt | None:
        """Return the Prompt together with the current PromptVersion loaded.

        Equivalent to a JOIN on current_version_id.  Returns None if the
        prompt does not exist.
        """
        ...

    async def update(self, prompt: Prompt) -> Prompt:
        """Persist in-place metadata changes (name, tags, status, current_version_id).

        Callers are responsible for lifecycle validation before calling this.
        """
        ...

    async def list(self, filters: PromptFilters) -> list[Prompt]:
        """Return a page of Prompts matching *filters* (spec §6.1)."""
        ...

    async def find_by_imported_from(self, imported_from: str) -> Prompt | None:
        """Return the Prompt with the given imported_from path, or None.

        Used for idempotency checks in the CLI import tool (spec §4 FR-7).
        """
        ...


class PromptVersionRepo(Protocol):
    """Immutable versioned body snapshots for a Prompt."""

    async def save(self, version: PromptVersion) -> PromptVersion:
        """Insert a new PromptVersion row and return it with DB-assigned created_at."""
        ...

    async def get(self, version_id: str) -> PromptVersion | None:
        """Return a PromptVersion by its id, or None if not found."""
        ...

    async def get_by_prompt_and_number(self, prompt_id: str, version: int) -> PromptVersion | None:
        """Return the PromptVersion with the given (prompt_id, version) number."""
        ...

    async def list_for_prompt(self, prompt_id: str) -> list[PromptVersion]:
        """Return all versions for a Prompt, ordered by version ASC."""
        ...

    async def list_by_prompt(
        self,
        prompt_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Return a paginated page of versions for a Prompt, ordered by version DESC.

        Returns (items, total) where total is the count of all versions for this prompt.
        Used by GET /api/prompts/{id}/versions for the A/B trigger dialog.
        """
        ...

    async def next_version_number(self, prompt_id: str) -> int:
        """Return the next sequential version number for the given prompt.

        Implementation must be safe under concurrent writes (e.g. SELECT MAX + 1
        inside the same transaction, or use a DB sequence).
        """
        ...


class PromptUsageRepo(Protocol):
    """Usage tracking: which StyleVersion nodes reference which PromptVersion."""

    async def save(self, usage: PromptUsage) -> PromptUsage:
        """Insert or upsert a PromptUsage record."""
        ...

    async def get(self, usage_id: str) -> PromptUsage | None:
        """Return a PromptUsage by its id, or None."""
        ...

    async def list_for_prompt(
        self, prompt_id: str, limit: int = 20, offset: int = 0
    ) -> list[PromptUsage]:
        """Return usages for a given Prompt, ordered by created_at DESC."""
        ...

    async def count_for_prompt(self, prompt_id: str) -> int:
        """Return the total number of usages for the given Prompt."""
        ...

    async def update_run_score(
        self,
        usage_id: str,
        score: float,
    ) -> PromptUsage | None:
        """Update last_run_score and last_run_at for the given usage record."""
        ...


class PromptAbComparisonRepo(Protocol):
    """Persistence for A/B comparison records (spec §4 FR-8, §13 단계 5)."""

    async def save(self, comparison: PromptAbComparison) -> PromptAbComparison:
        """Insert a new PromptAbComparison row and return it with DB-assigned timestamps."""
        ...

    async def get(self, ab_id: str) -> PromptAbComparison | None:
        """Return a PromptAbComparison by its id, or None if not found."""
        ...

    async def update(self, comparison: PromptAbComparison) -> PromptAbComparison:
        """Persist changes to from_run_id, to_run_id, status, finished_at, started_at."""
        ...
