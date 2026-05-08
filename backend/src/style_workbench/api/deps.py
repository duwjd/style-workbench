from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.infra.db.session import get_db
from style_workbench.infra.repositories.run_repo import SqlAlchemyRunRepository
from style_workbench.infra.repositories.style_repo import SqlAlchemyStyleRepository
from style_workbench.services.run_service import RunService
from style_workbench.services.style_service import StyleService
from style_workbench.services.variant_service import VariantService

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_style_service(session: DbSession) -> StyleService:
    return StyleService(repo=SqlAlchemyStyleRepository(session))


def get_variant_service(session: DbSession) -> VariantService:
    return VariantService(repo=SqlAlchemyStyleRepository(session))


def get_run_service(session: DbSession) -> RunService:
    return RunService(
        style_repo=SqlAlchemyStyleRepository(session),
        run_repo=SqlAlchemyRunRepository(session),
        session=session,
    )
