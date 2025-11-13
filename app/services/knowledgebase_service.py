from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from config.models import KnowledgeBase, Datasource
from schemas.knowledgebase_schema import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
)
from exceptions.custom_errors import (
    NotFoundException,
    ConflictException,
    BadRequestException,
)


def get_knowledge_base_by_id(
    db: Session, knowledge_base_id: int, user_id: int
) -> Optional[KnowledgeBase]:
    """Get a knowledge base by ID for a specific user"""
    return (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .first()
    )


def get_user_knowledge_bases(
    db: Session, user_id: int, include_stats: bool = False
) -> list[KnowledgeBase]:
    """Get all knowledge bases for a user"""
    knowledge_bases = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .order_by(KnowledgeBase.is_enabled.desc(), KnowledgeBase.created_at.desc())
        .all()
    )

    if include_stats:
        # Add file count and total size to each knowledge base
        for kb in knowledge_bases:
            stats = (
                db.query(
                    func.count(Datasource.id).label("file_count"),
                    func.coalesce(func.sum(Datasource.file_size), 0).label(
                        "total_size"
                    ),
                )
                .filter(
                    Datasource.knowledge_base_id == kb.id,
                    Datasource.deleted_at.is_(None),
                )
                .first()
            )
            kb.file_count = stats.file_count if stats else 0
            kb.total_size = stats.total_size if stats else 0

    return knowledge_bases


def get_enabled_knowledge_base(db: Session, user_id: int) -> Optional[KnowledgeBase]:
    """Get the currently enabled knowledge base for a user"""
    return (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.is_enabled == True,
            KnowledgeBase.deleted_at.is_(None),
        )
        .first()
    )


def create_knowledge_base(
    db: Session, user_id: int, data: KnowledgeBaseCreate
) -> KnowledgeBase:
    """Create a new knowledge base"""
    # Check maximum limit (6 knowledge bases per user)
    count = (
        db.query(func.count(KnowledgeBase.id))
        .filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .scalar()
    )

    if count >= 6:
        raise BadRequestException("Maximum 6 knowledge bases allowed per user")

    # Check if name already exists for this user
    existing = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.name == data.name,
            KnowledgeBase.deleted_at.is_(None),
        )
        .first()
    )

    if existing:
        raise ConflictException(
            f"Knowledge base with name '{data.name}' already exists"
        )

    # If this is being created as enabled, disable all others
    if data.is_enabled:
        db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.deleted_at.is_(None),
        ).update({"is_enabled": False})

    # Create new knowledge base
    knowledge_base = KnowledgeBase(
        user_id=user_id,
        name=data.name,
        description=data.description,
        is_enabled=data.is_enabled,
    )

    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)

    return knowledge_base


def update_knowledge_base(
    db: Session, knowledge_base_id: int, user_id: int, data: KnowledgeBaseUpdate
) -> KnowledgeBase:
    """Update a knowledge base"""
    knowledge_base = get_knowledge_base_by_id(db, knowledge_base_id, user_id)

    if not knowledge_base:
        raise NotFoundException("Knowledge base not found")

    # Check if new name conflicts with existing
    if data.name and data.name != knowledge_base.name:
        existing = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.name == data.name,
                KnowledgeBase.id != knowledge_base_id,
                KnowledgeBase.deleted_at.is_(None),
            )
            .first()
        )

        if existing:
            raise ConflictException(
                f"Knowledge base with name '{data.name}' already exists"
            )

    # Update fields
    if data.name is not None:
        knowledge_base.name = data.name
    if data.description is not None:
        knowledge_base.description = data.description

    db.commit()
    db.refresh(knowledge_base)

    return knowledge_base


def toggle_knowledge_base(
    db: Session, knowledge_base_id: int, user_id: int, is_enabled: bool
) -> KnowledgeBase:
    """Toggle knowledge base enabled status"""
    knowledge_base = get_knowledge_base_by_id(db, knowledge_base_id, user_id)

    if not knowledge_base:
        raise NotFoundException("Knowledge base not found")

    # If enabling, disable all others
    if is_enabled:
        db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.id != knowledge_base_id,
            KnowledgeBase.deleted_at.is_(None),
        ).update({"is_enabled": False})

    knowledge_base.is_enabled = is_enabled

    db.commit()
    db.refresh(knowledge_base)

    return knowledge_base


def delete_knowledge_base(db: Session, knowledge_base_id: int, user_id: int) -> None:
    """Delete a knowledge base (soft delete)"""
    knowledge_base = get_knowledge_base_by_id(db, knowledge_base_id, user_id)

    if not knowledge_base:
        raise NotFoundException("Knowledge base not found")

    # Check if this is the last knowledge base
    total_count = (
        db.query(func.count(KnowledgeBase.id))
        .filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .scalar()
    )

    if total_count <= 1:
        raise BadRequestException(
            "Cannot delete the last knowledge base. At least one must exist."
        )

    # Soft delete
    knowledge_base.deleted_at = func.now()

    db.commit()


def get_or_create_default_knowledge_base(db: Session, user_id: int) -> KnowledgeBase:
    """
    Get or create a default knowledge base for a user.
    Used during user signup/signin to ensure every user has at least one knowledge base.
    """
    # Check if user has any knowledge base
    existing = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .first()
    )

    if existing:
        return existing

    # Create default knowledge base
    default_kb = KnowledgeBase(
        user_id=user_id,
        name="General Knowledge",
        description="Default knowledge base for general documents",
        is_enabled=True,  # First knowledge base is enabled by default
    )

    db.add(default_kb)
    db.commit()
    db.refresh(default_kb)

    return default_kb
