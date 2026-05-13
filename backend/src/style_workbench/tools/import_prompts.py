"""CLI tool: import_prompts — bulk import external prompt files into the Prompt Library.

Spec §4 FR-7 / §13 단계 4.

Usage::

    uv run python -m style_workbench.tools.import_prompts --source <directory>

Options:
    --source    Path to the source directory (required).
                Files are walked recursively.
    --db-url    Database URL (overrides DATABASE_URL env var).
    --dry-run   Print what would be imported without writing to DB.

File → Prompt mapping rules (spec §4 FR-7):
    node_type:
        *_text.md / *_text.txt      → "text"
        *_image.md / *_image.txt    → "image"
        *_video.md / *_video.txt    → "video"
        *_composition.md / *_composition.txt → "composition"
        (no match)                  → "text" + WARNING

    name: filename with extension and *_<node_type> suffix removed.
    tags: ancestor directory names between <source> and the file.
    body: file contents (UTF-8).
    declared_variables: extract_placeholders(body) — all required=True, role="unknown".
    imported_from: absolute path string (idempotency key).
    status: "approved" (externally validated assets).
    created_by: "tool:import_prompts".

Idempotency:
    If a Prompt with the same imported_from already exists, the file is skipped.
    The tool can be re-run safely.

Exit codes:
    0 — all files imported (or already existed / skipped).
    1 — one or more files failed to import.
    2 — fatal error (bad arguments, DB unreachable, etc.).

Security / CLAUDE.md §9:
    - prompt body MUST NOT appear in logs.  Only body_hash is logged.
    - No external SDK imports (anthropic / openai / replicate).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import traceback
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from style_workbench.core.config import settings
from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    NodeType,
    PromptStatus,
)
from style_workbench.domain.prompt.template import extract_placeholders
from style_workbench.infra.repositories.prompt_repo import (
    SqlAlchemyPromptRepo,
    SqlAlchemyPromptUsageRepo,
    SqlAlchemyPromptVersionRepo,
)
from style_workbench.services.prompt_service import PromptService

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NODE_TYPE_SUFFIXES: dict[str, NodeType] = {
    "_text": NodeType.TEXT,
    "_image": NodeType.IMAGE,
    "_video": NodeType.VIDEO,
    "_composition": NodeType.COMPOSITION,
}

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".md", ".txt"})

_CREATED_BY = "tool:import_prompts"


# ---------------------------------------------------------------------------
# File → domain mapping helpers
# ---------------------------------------------------------------------------


def _resolve_node_type(stem: str) -> tuple[NodeType, bool]:
    """Return (node_type, is_matched) based on the file stem suffix.

    Tries each suffix in a deterministic order.  Returns (TEXT, False) as the
    default when no suffix matches.
    """
    for suffix, node_type in _NODE_TYPE_SUFFIXES.items():
        if stem.endswith(suffix):
            return node_type, True
    return NodeType.TEXT, False


def _clean_name(stem: str, node_type: NodeType) -> str:
    """Strip the *_<node_type> suffix from the stem to derive the prompt name.

    Example:
        "biz_portrait_image" → "biz_portrait"  (when node_type == IMAGE)
        "greeting"           → "greeting"       (no suffix to strip)
    """
    suffix = f"_{node_type.value}"
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


def _extract_tags(file_path: Path, source_root: Path) -> list[str]:
    """Return the list of ancestor directory names between source_root and file_path.

    Example:
        source_root = /data/prompts
        file_path   = /data/prompts/portrait/professional/biz_portrait_image.md
        → ["portrait", "professional"]
    """
    try:
        relative = file_path.relative_to(source_root)
    except ValueError:
        return []
    # parts = ("portrait", "professional", "biz_portrait_image.md")
    # We want the directory parts only (exclude the filename itself).
    return list(relative.parts[:-1])


def _body_hash(body: str) -> str:
    """Short SHA-256 digest for structured logging (CLAUDE.md §9)."""
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _build_declared_variables(body: str) -> list[DeclaredVariable]:
    """Extract placeholders from *body* and convert to DeclaredVariable list.

    All variables are marked required=True, role="unknown" as per spec §4 FR-7.
    """
    names = extract_placeholders(body)
    return [DeclaredVariable(name=name, role="unknown", required=True) for name in sorted(names)]


# ---------------------------------------------------------------------------
# Per-file import logic (sync helper, run inside asyncio.to_thread)
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    """Read file contents as UTF-8 text.

    Raises:
        UnicodeDecodeError: if the file is not valid UTF-8.
        OSError: if the file cannot be opened.
        ValueError: if the file is empty.
    """
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"File is empty: {path}")
    return content


# ---------------------------------------------------------------------------
# Async core — database import
# ---------------------------------------------------------------------------


async def _import_one(
    file_path: Path,
    source_root: Path,
    service: PromptService,
    dry_run: bool,
) -> str:
    """Import a single file into the Prompt Library.

    Returns: "imported" | "skipped"
    Raises on error (caller aggregates into error list).
    """
    stem = file_path.stem
    node_type, matched = _resolve_node_type(stem)
    name = _clean_name(stem, node_type)
    tags = _extract_tags(file_path, source_root)
    imported_from = str(file_path.resolve())

    if not matched:
        logger.warning(
            "node_type_undetected",
            file=str(file_path),
            defaulting_to="text",
        )

    body = await asyncio.to_thread(_read_file, file_path)
    declared_variables = _build_declared_variables(body)

    log = logger.bind(
        file=str(file_path),
        name=name,
        node_type=str(node_type),
        tags=tags,
        imported_from=imported_from,
        body_hash=_body_hash(body),
        declared_vars=[v.name for v in declared_variables],
    )

    if dry_run:
        log.info("dry_run_would_import")
        return "imported"

    # Idempotency: check existing by imported_from via PromptService helper.
    # Uses the find_by_imported_from method added to PromptService (spec §4 FR-7).
    existing = await service.find_by_imported_from(imported_from)
    if existing is not None:
        log.info("import_skipped_already_exists")
        return "skipped"

    await service.create(
        name=name,
        node_type=node_type,
        body=body,
        declared_variables=declared_variables,
        tags=tags,
        imported_from=imported_from,
        initial_status=PromptStatus.APPROVED,
        created_by=_CREATED_BY,
    )
    log.info("import_ok")
    return "imported"


# ---------------------------------------------------------------------------
# Walk directory
# ---------------------------------------------------------------------------


def _walk_prompt_files(source: Path) -> list[Path]:
    """Recursively collect .md and .txt files under *source* (sorted for determinism)."""
    found: list[Path] = []
    for ext in _SUPPORTED_EXTENSIONS:
        found.extend(source.rglob(f"*{ext}"))
    return sorted(set(found))


# ---------------------------------------------------------------------------
# Main async entrypoint
# ---------------------------------------------------------------------------


async def run_import(
    source: Path,
    db_url: str | None,
    dry_run: bool,
) -> int:
    """Core import logic.  Returns the process exit code (0 / 1 / 2).

    Separated from main() to enable direct invocation in tests.
    """
    effective_db_url = db_url or settings.database_url

    if not source.exists():
        print(f"ERROR: source directory not found: {source}", file=sys.stderr)
        return 2
    if not source.is_dir():
        print(f"ERROR: source is not a directory: {source}", file=sys.stderr)
        return 2

    files = _walk_prompt_files(source)
    if not files:
        print(f"WARNING: no .md or .txt files found under: {source}", file=sys.stderr)
        print("0 imported, 0 skipped, 0 errored")
        return 0

    engine = create_async_engine(effective_db_url, echo=False)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    n_imported = 0
    n_skipped = 0
    errors: list[tuple[Path, str]] = []

    try:
        # Each file is imported in its own session/transaction so that a failure
        # on one file does not block the remaining files.
        for file_path in files:
            async with SessionFactory() as session:
                try:
                    prompt_repo: SqlAlchemyPromptRepo = SqlAlchemyPromptRepo(session)
                    version_repo: SqlAlchemyPromptVersionRepo = SqlAlchemyPromptVersionRepo(session)
                    usage_repo: SqlAlchemyPromptUsageRepo = SqlAlchemyPromptUsageRepo(session)
                    service = PromptService(
                        prompt_repo=prompt_repo,
                        version_repo=version_repo,
                        usage_repo=usage_repo,
                    )

                    result = await _import_one(
                        file_path=file_path,
                        source_root=source,
                        service=service,
                        dry_run=dry_run,
                    )
                    if not dry_run:
                        await session.commit()
                    if result == "imported":
                        n_imported += 1
                    else:
                        n_skipped += 1
                except Exception as exc:  # noqa: BLE001
                    await session.rollback()
                    err_msg = f"{type(exc).__name__}: {exc}"
                    print(f"ERROR [{file_path}]: {err_msg}", file=sys.stderr)
                    errors.append((file_path, err_msg))
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: unexpected error — {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    # Summary line (always printed to stdout)
    n_errored = len(errors)
    print(f"{n_imported} imported, {n_skipped} skipped, {n_errored} errored")

    if errors:
        print("\nFailed files:", file=sys.stderr)
        for path, msg in errors:
            print(f"  {path}: {msg}", file=sys.stderr)
        return 1

    return 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_prompts",
        description=(
            "Import external prompt files (.md / .txt) into the Style Workbench Prompt Library.\n\n"
            "File-naming convention determines node_type:\n"
            "  *_text.md | *_text.txt         → text\n"
            "  *_image.md | *_image.txt        → image\n"
            "  *_video.md | *_video.txt        → video\n"
            "  *_composition.md | *_composition.txt → composition\n"
            "  (no suffix match)               → text (with WARNING)\n\n"
            "Idempotent: files already imported (by path) are skipped on re-run.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        required=True,
        metavar="<path>",
        help="Path to the source directory.  Recursively walked for .md / .txt files.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        metavar="<url>",
        help=(
            "PostgreSQL async URL (e.g. postgresql+asyncpg://user:pass@host/db). "
            "Overrides the DATABASE_URL environment variable."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be imported without writing to the database.",
    )
    return parser


def main() -> None:
    """Entry point for `python -m style_workbench.tools.import_prompts`."""
    parser = _build_parser()
    args = parser.parse_args()

    source = Path(args.source)
    exit_code = asyncio.run(
        run_import(
            source=source,
            db_url=args.db_url,
            dry_run=args.dry_run,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
