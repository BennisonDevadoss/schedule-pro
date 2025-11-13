from typing import Annotated, Any, Optional

from fastapi import APIRouter, status, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session

from services import datasource_service
from config.models import User
from config.logger import logger
from config.constants import USER_ROLES
from lib.pagination import paginate, paginator_result
from config.database import get_db
from dependencies.auth import AuthenticateUser
from schemas.datasource_schema import (
    CrawlResponse,
    DatasourceStats,
    CrawlUrlsRequest,
    FileUploadResponse,
    TaskStatusResponse,
    DatasourceResponse,
)

# Enterprise Standard: RESTful Hierarchy
knowledgebase_datasource_router = APIRouter(
    prefix="/knowledgebase",
    tags=["knowledgebase-datasources"],
    dependencies=[
        Depends(AuthenticateUser([USER_ROLES.ADMIN]))
    ],  # All endpoints protected
)

# Task status router (not under KB hierarchy)
datasource_router = APIRouter(
    prefix="/datasource",
    tags=["datasource"],
    dependencies=[
        Depends(AuthenticateUser([USER_ROLES.ADMIN]))
    ],  # All endpoints protected
)


# ==================== FILE UPLOAD ENDPOINTS ====================


@knowledgebase_datasource_router.post(
    "/{knowledge_base_id}/datasources/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_file(
    knowledge_base_id: int,
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """
    Upload file for processing in knowledge base.
    File will be processed asynchronously.
    Creates datasource record immediately with 'pending' status.
    """
    try:
        task = datasource_service.start_file_upload_task(
            knowledge_base_id, file, db, current_user.id
        )
        return FileUploadResponse(message="File processing started", task_id=task.id)
    except Exception as e:
        logger.exception(e)
        raise e


# ==================== URL CRAWLING ENDPOINTS ====================


@knowledgebase_datasource_router.post(
    "/{knowledge_base_id}/datasources/crawl",
    response_model=CrawlResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def crawl_urls(
    knowledge_base_id: int,
    urls_request: CrawlUrlsRequest,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> CrawlResponse:
    """
    Start URL crawling for knowledge base.
    URLs will be crawled and processed asynchronously.
    Creates datasource records immediately with 'pending' status for each URL.
    """
    try:
        task = datasource_service.start_crawl_task(
            knowledge_base_id=knowledge_base_id,
            urls=urls_request.urls,
            db=db,
            user_id=current_user.id,
        )
        return CrawlResponse(message="Crawling started", task_id=task.id)
    except Exception as e:
        logger.exception(e)
        raise e


# ==================== TASK STATUS ENDPOINT ====================


@datasource_router.get(
    "/task/{task_id}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
) -> dict[str, Any]:
    """
    Get status of an async task (upload/crawl).
    """
    try:
        return datasource_service.get_task_status(task_id)
    except Exception as e:
        logger.exception(e)
        raise e


# ==================== DATASOURCE MANAGEMENT ENDPOINTS ====================


@knowledgebase_datasource_router.get(
    "/{knowledge_base_id}/datasources",
    status_code=status.HTTP_200_OK,
)
async def get_datasources(
    knowledge_base_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    """
    Get all datasources in a specific knowledge base with pagination.
    Returns: {"datasources": [...], "pagination": {...}}
    """
    try:
        # Validate and normalize pagination params
        page = page if page > 0 else 1
        per_page = per_page if per_page > 0 and per_page <= 100 else 10

        # Calculate skip
        skip = (page - 1) * per_page

        # Get datasources and total count
        datasources, total = datasource_service.get_user_datasources(
            db, current_user.id, knowledge_base_id, status_filter, skip, per_page
        )

        # ✅ Convert SQLAlchemy models to Pydantic schemas
        datasource_responses = [
            DatasourceResponse.model_validate(datasource) for datasource in datasources
        ]

        # Create pagination metadata
        pagination_meta = paginator_result(total, page, per_page)

        # Return paginated response
        return paginate(pagination_meta, datasource_responses, "datasources")
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_datasource_router.get(
    "/{knowledge_base_id}/datasources/{datasource_id}",
    response_model=DatasourceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_datasource(
    knowledge_base_id: int,
    datasource_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> DatasourceResponse:
    """
    Get a specific datasource by ID.
    """
    try:
        datasource = datasource_service.get_datasource_by_id(
            db, datasource_id, current_user.id
        )
        if not datasource:
            from exceptions.custom_errors import NotFoundException

            raise NotFoundException("Datasource not found")

        # Verify datasource belongs to the knowledge base
        if datasource.knowledge_base_id != knowledge_base_id:
            from exceptions.custom_errors import NotFoundException

            raise NotFoundException("Datasource not found in this knowledge base")

        return datasource
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_datasource_router.delete(
    "/{knowledge_base_id}/datasources/{datasource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_datasource(
    knowledge_base_id: int,
    datasource_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a datasource (soft delete).
    """
    try:
        # Verify datasource belongs to the knowledge base
        datasource = datasource_service.get_datasource_by_id(
            db, datasource_id, current_user.id
        )
        if not datasource or datasource.knowledge_base_id != knowledge_base_id:
            from exceptions.custom_errors import NotFoundException

            raise NotFoundException("Datasource not found in this knowledge base")

        datasource_service.delete_datasource(db, datasource_id, current_user.id)
    except Exception as e:
        logger.exception(e)
        raise e


@knowledgebase_datasource_router.get(
    "/{knowledge_base_id}/datasources/stats",
    response_model=DatasourceStats,
    status_code=status.HTTP_200_OK,
)
async def get_datasource_stats(
    knowledge_base_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> DatasourceStats:
    """
    Get statistics for datasources in a knowledge base.
    """
    try:
        # Get datasources for this KB
        datasources, total = datasource_service.get_user_datasources(
            db, current_user.id, knowledge_base_id, None, 0, 10000
        )

        completed = sum(1 for d in datasources if d.status == "completed")
        processing = sum(1 for d in datasources if d.status == "processing")
        failed = sum(1 for d in datasources if d.status == "failed")
        total_size = sum(d.file_size or 0 for d in datasources)

        return DatasourceStats(
            total=total,
            completed=completed,
            processing=processing,
            failed=failed,
            total_size_bytes=total_size,
        )
    except Exception as e:
        logger.exception(e)
        raise e
