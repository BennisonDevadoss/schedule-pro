from typing import Annotated

from fastapi import APIRouter, status, Depends, Query
from sqlalchemy.orm import Session

from services import knowledgebase_service
from config.models import User
from config.logger import logger
from config.database import get_db
from config.constants import USER_ROLES
from dependencies.auth import AuthenticateUser
from schemas.knowledgebase_schema import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseToggle,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseStatsResponse,
)

knowledgebase_router = APIRouter(prefix="/knowledgebase", tags=["knowledgebase"])


@knowledgebase_router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_knowledge_bases(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
    include_stats: bool = Query(False, description="Include file count and size stats"),
) -> KnowledgeBaseListResponse:
    """
    Get all knowledge bases for the authenticated user.
    """
    try:
        knowledge_bases = knowledgebase_service.get_user_knowledge_bases(
            db, current_user.id, include_stats
        )
        return KnowledgeBaseListResponse(
            total=len(knowledge_bases), knowledge_bases=knowledge_bases
        )
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_router.get(
    "/stats",
    response_model=KnowledgeBaseStatsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_knowledge_base_stats(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> KnowledgeBaseStatsResponse:
    """
    Get statistics about user's knowledge bases.
    """
    try:
        from sqlalchemy import func
        from config.models import KnowledgeBase, Datasource

        # Get total knowledge bases
        total_kb = (
            db.query(func.count(KnowledgeBase.id))
            .filter(
                KnowledgeBase.user_id == current_user.id,
                KnowledgeBase.deleted_at.is_(None),
            )
            .scalar()
        )

        # Get enabled knowledge base
        enabled_kb = knowledgebase_service.get_enabled_knowledge_base(
            db, current_user.id
        )

        # Get total files and size across all knowledge bases
        stats = (
            db.query(
                func.count(Datasource.id).label("total_files"),
                func.coalesce(func.sum(Datasource.file_size), 0).label("total_size"),
            )
            .filter(
                Datasource.user_id == current_user.id, Datasource.deleted_at.is_(None)
            )
            .first()
        )

        return KnowledgeBaseStatsResponse(
            total_knowledge_bases=total_kb or 0,
            enabled_knowledge_base=enabled_kb,
            total_files=stats.total_files if stats else 0,
            total_size_bytes=stats.total_size if stats else 0,
        )
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_router.get(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
)
async def get_knowledge_base(
    knowledge_base_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> KnowledgeBaseResponse:
    """
    Get a specific knowledge base by ID.
    """
    try:
        knowledge_base = knowledgebase_service.get_knowledge_base_by_id(
            db, knowledge_base_id, current_user.id
        )
        if not knowledge_base:
            from exceptions.custom_errors import NotFoundException

            raise NotFoundException("Knowledge base not found")
        return knowledge_base
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> KnowledgeBaseResponse:
    """
    Create a new knowledge base.
    """
    try:
        knowledge_base = knowledgebase_service.create_knowledge_base(
            db, current_user.id, data
        )
        return knowledge_base
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_router.put(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
)
async def update_knowledge_base(
    knowledge_base_id: int,
    data: KnowledgeBaseUpdate,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> KnowledgeBaseResponse:
    """
    Update a knowledge base.
    """
    try:
        knowledge_base = knowledgebase_service.update_knowledge_base(
            db, knowledge_base_id, current_user.id, data
        )
        return knowledge_base
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_router.patch(
    "/{knowledge_base_id}/toggle",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
)
async def toggle_knowledge_base(
    knowledge_base_id: int,
    data: KnowledgeBaseToggle,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> KnowledgeBaseResponse:
    """
    Toggle knowledge base enabled status.
    When enabled, all other knowledge bases are automatically disabled.
    """
    try:
        knowledge_base = knowledgebase_service.toggle_knowledge_base(
            db, knowledge_base_id, current_user.id, data.is_enabled
        )
        return knowledge_base
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_router.delete(
    "/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_base(
    knowledge_base_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a knowledge base (soft delete).
    Cannot delete if it's the last knowledge base - at least one must exist.
    """
    try:
        knowledgebase_service.delete_knowledge_base(
            db, knowledge_base_id, current_user.id
        )
    except Exception as e:
        logger.exception(e)
        raise e
