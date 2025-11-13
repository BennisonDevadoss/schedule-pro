from typing import Optional
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from config.models import Conversation, Message
from exceptions.custom_errors import NotFoundException


def get_user_conversations(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 10,
    knowledge_base_id: Optional[int] = None,
) -> tuple[list[Conversation], int]:
    """Get user's conversations with pagination"""
    query = db.query(Conversation).filter(Conversation.user_id == user_id)

    # Filter by KB if provided
    if knowledge_base_id:
        query = query.filter(Conversation.knowledge_base_id == knowledge_base_id)

    # Get total count
    total = query.count()

    # Get paginated results
    conversations = (
        query.order_by(desc(Conversation.started_at)).offset(skip).limit(limit).all()
    )

    return conversations, total


def get_conversation_by_id(
    db: Session, conversation_id: int, user_id: int
) -> Conversation:
    """Get conversation by ID with messages"""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )

    if not conversation:
        raise NotFoundException("Conversation not found")

    return conversation


def create_conversation(
    db: Session, user_id: int, session_id: str, user_identifier: Optional[str] = None
) -> Conversation:
    """Create a new conversation"""
    conversation = Conversation(
        user_id=user_id,
        session_id=session_id,
        user_identifier=user_identifier,
        status="active",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def add_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    knowledge_base_id: Optional[int] = None,
) -> Message:
    """Add a message to conversation with KB tracking"""
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        knowledge_base_id=knowledge_base_id,
    )
    db.add(message)

    # Update conversation metadata
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if conversation:
        conversation.message_count += 1
        if not conversation.first_message and role == "user":
            conversation.first_message = content[:100]  # Store first 100 chars
        conversation.updated_at = datetime.now()

    db.commit()
    db.refresh(message)
    return message


def end_conversation(db: Session, conversation_id: int) -> None:
    """Mark conversation as ended"""
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if conversation:
        conversation.status = "ended"
        conversation.ended_at = datetime.now()
        db.commit()
