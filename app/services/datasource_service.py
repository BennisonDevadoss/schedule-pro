import shutil
from typing import List, Any, Optional
from datetime import datetime
from tempfile import NamedTemporaryFile

from fastapi import UploadFile
from sqlalchemy import func
from celery.result import AsyncResult
from sqlalchemy.orm import Session

from queues.tasks import crawl_urls_task, upload_file_task
from queues.worker import celery_app
from config.vector_db import vector_db
from config.models import Datasource
from exceptions.custom_errors import NotFoundException
from schemas.datasource_schema import DatasourceCreate, DatasourceUpdate


# FIXME: this is the temp function (document ingestion process should be executed inside celery tasks.)
def upload_file(
    _: str, file: UploadFile
) -> str:  # collection_name is passed like _ (underscore)
    with NamedTemporaryFile(delete=True, suffix=f"_{file.filename}") as tmp:
        shutil.copyfileobj(file.file, tmp)
        file_path = tmp.name

        documents = vector_db.load_and_split(file_path)
        vector_db.ingest_documents(documents)

    return "File is been ingested to Vector DB successfully!!!"


def start_crawl_task(
    knowledge_base_id: int, urls: List[str], db: Session, user_id: int
) -> Any:
    """Start URL crawl task and create datasource records for each URL"""
    datasource_ids = []

    # Create a datasource record for each URL
    for url in urls:
        datasource = Datasource(
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            file_name=url,  # Store URL as file_name for crawled content
            file_type="url",
            status="pending",
        )
        db.add(datasource)
        db.commit()
        db.refresh(datasource)
        datasource_ids.append(datasource.id)

    # Start async task with datasource IDs
    task = crawl_urls_task.delay(
        knowledge_base_id=knowledge_base_id, urls=urls, datasource_ids=datasource_ids
    )

    # ✅ Store task_id in all datasource records
    for datasource_id in datasource_ids:
        datasource = db.query(Datasource).filter(Datasource.id == datasource_id).first()
        if datasource:
            datasource.task_id = task.id
    db.commit()

    return task


def start_file_upload_task(
    knowledge_base_id: int, file: UploadFile, db: Session, user_id: int
) -> Any:
    """Start file upload task and create datasource record"""
    import os

    # Get file info
    file_type = file.filename.split(".")[-1] if "." in file.filename else "unknown"

    # Save file temporarily (delete=False keeps file after closing)
    tmp = NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
    try:
        # Copy file content
        shutil.copyfileobj(file.file, tmp)
        tmp.flush()  # Ensure all data is written
        file_size = tmp.tell()
        file_path = tmp.name
    finally:
        tmp.close()  # Close but don't delete (delete=False)

    # Create datasource record with pending status
    datasource = Datasource(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        file_name=file.filename,
        file_type=file_type,
        file_size=file_size,
        status="pending",
    )
    db.add(datasource)
    db.commit()
    db.refresh(datasource)

    # Start async task with datasource ID
    task = upload_file_task.delay(knowledge_base_id, file_path, datasource.id)

    # ✅ Store task_id for tracking and cancellation
    datasource.task_id = task.id
    db.commit()

    return task


def get_task_status(task_id: str) -> dict[str, Any]:
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": str(task_result.result) if task_result.result else None,
    }
    return response


# User Datasource Metadata Functions
def get_datasource_by_id(
    db: Session, datasource_id: int, user_id: int
) -> Optional[Datasource]:
    """Get a specific datasource by ID for a user"""
    return (
        db.query(Datasource)
        .filter(
            Datasource.id == datasource_id,
            Datasource.user_id == user_id,
            Datasource.deleted_at.is_(None),
        )
        .first()
    )


def get_user_datasources(
    db: Session,
    user_id: int,
    knowledge_base_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Datasource], int]:
    """
    Get all datasources for a user with optional filters.
    Returns (datasources, total_count)
    """
    query = db.query(Datasource).filter(
        Datasource.user_id == user_id,
        Datasource.deleted_at.is_(None),
    )

    # Apply filters
    if knowledge_base_id:
        query = query.filter(Datasource.knowledge_base_id == knowledge_base_id)
    if status:
        query = query.filter(Datasource.status == status)

    # Get total count
    total = query.count()

    # Get paginated results
    datasources = (
        query.order_by(Datasource.created_at.desc()).offset(skip).limit(limit).all()
    )

    return datasources, total


def create_datasource(
    db: Session, user_id: int, datasource_data: DatasourceCreate
) -> Datasource:
    """Create a new datasource entry for a user"""
    datasource = Datasource(
        user_id=user_id,
        knowledge_base_id=datasource_data.knowledge_base_id,
        file_name=datasource_data.file_name,
        file_type=datasource_data.file_type,
        file_size=datasource_data.file_size,
        collection_name=datasource_data.collection_name,  # Keep for backward compatibility
        description=datasource_data.description,
        tags=datasource_data.tags,
        external_id=datasource_data.external_id,
        vector_db_collection=datasource_data.vector_db_collection,
        status="pending",
    )

    db.add(datasource)
    db.commit()
    db.refresh(datasource)
    return datasource


def update_datasource(
    db: Session, datasource_id: int, user_id: int, datasource_data: DatasourceUpdate
) -> Datasource:
    """Update a datasource entry"""
    datasource = get_datasource_by_id(db, datasource_id, user_id)

    if not datasource:
        raise NotFoundException("Datasource not found")

    # Update only provided fields
    update_data = datasource_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(datasource, field, value)

    db.commit()
    db.refresh(datasource)
    return datasource


def update_datasource_status(
    db: Session,
    datasource_id: int,
    user_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> Datasource:
    """Update datasource processing status"""
    datasource = get_datasource_by_id(db, datasource_id, user_id)

    if not datasource:
        raise NotFoundException("Datasource not found")

    datasource.status = status
    if error_message:
        datasource.error_message = error_message

    if status == "completed":
        datasource.processed_at = datetime.now()

    db.commit()
    db.refresh(datasource)
    return datasource


def delete_datasource(db: Session, datasource_id: int, user_id: int) -> None:
    """Soft delete a datasource entry and cancel running tasks"""
    from config.logger import logger

    datasource = get_datasource_by_id(db, datasource_id, user_id)

    if not datasource:
        raise NotFoundException("Datasource not found")

    # ✅ Mark as deleted FIRST (prevents race conditions)
    datasource.deleted_at = datetime.now()
    db.commit()

    # ✅ Revoke task if it's pending or processing
    if datasource.task_id and datasource.status in ["pending", "processing"]:
        try:
            # Terminate=True forcefully stops the task
            AsyncResult(datasource.task_id, app=celery_app).revoke(terminate=True)
            logger.info(
                f"Revoked task {datasource.task_id} for datasource {datasource_id}"
            )

            # Update status to cancelled
            datasource.status = "cancelled"
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to revoke task {datasource.task_id}: {e}")
            # Continue with deletion even if revocation fails


def get_datasources_by_knowledge_base(
    db: Session, user_id: int, knowledge_base_id: int
) -> list[Datasource]:
    """Get all datasources in a specific knowledge base"""
    return (
        db.query(Datasource)
        .filter(
            Datasource.user_id == user_id,
            Datasource.knowledge_base_id == knowledge_base_id,
            Datasource.deleted_at.is_(None),
        )
        .order_by(Datasource.created_at.desc())
        .all()
    )


def get_user_collections(db: Session, user_id: int) -> list[str]:
    """Get list of unique collection names for a user (DEPRECATED - use knowledge bases instead)"""
    collections = (
        db.query(Datasource.collection_name)
        .filter(
            Datasource.user_id == user_id,
            Datasource.deleted_at.is_(None),
        )
        .distinct()
        .all()
    )
    return [c[0] for c in collections if c[0]]  # Filter out None values


def get_datasource_stats(db: Session, user_id: int) -> dict:
    """Get statistics about user's datasources"""
    total = (
        db.query(func.count(Datasource.id))
        .filter(
            Datasource.user_id == user_id,
            Datasource.deleted_at.is_(None),
        )
        .scalar()
    )

    completed = (
        db.query(func.count(Datasource.id))
        .filter(
            Datasource.user_id == user_id,
            Datasource.status == "completed",
            Datasource.deleted_at.is_(None),
        )
        .scalar()
    )

    processing = (
        db.query(func.count(Datasource.id))
        .filter(
            Datasource.user_id == user_id,
            Datasource.status == "processing",
            Datasource.deleted_at.is_(None),
        )
        .scalar()
    )

    failed = (
        db.query(func.count(Datasource.id))
        .filter(
            Datasource.user_id == user_id,
            Datasource.status == "failed",
            Datasource.deleted_at.is_(None),
        )
        .scalar()
    )

    total_size = (
        db.query(func.sum(Datasource.file_size))
        .filter(
            Datasource.user_id == user_id,
            Datasource.deleted_at.is_(None),
        )
        .scalar()
    ) or 0

    return {
        "total": total,
        "completed": completed,
        "processing": processing,
        "failed": failed,
        "total_size_bytes": total_size,
    }
