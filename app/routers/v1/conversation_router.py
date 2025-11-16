import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from services import conversation_service
from config.logger import logger
from config.models import User
from lib.pagination import paginate, paginator_result
from config.database import get_db
from config.constants import USER_ROLES
from dependencies.auth import AuthenticateUser
from schemas.conversation_schema import (
    ConversationResponse,
    ConversationDetailResponse,
)

conversation_router = APIRouter(prefix="/conversations", tags=["Conversations"])


@conversation_router.post(
    "", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """
    Create a new conversation for testing.
    """
    try:
        # Generate unique session ID
        session_id = f"test-{uuid.uuid4()}"

        # Create conversation
        conversation = conversation_service.create_conversation(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            user_identifier="Test User",
        )

        return ConversationResponse.model_validate(conversation)
    except Exception as e:
        logger.exception(e)
        raise e


@conversation_router.get("", status_code=status.HTTP_200_OK)
async def get_conversations(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    knowledge_base_id: int = Query(None, description="Filter by knowledge base"),
) -> dict[str, Any]:
    """
    Get user's conversations with pagination.
    """
    try:
        # Validate pagination
        page = page if page > 0 else 1
        per_page = per_page if per_page > 0 and per_page <= 100 else 10
        skip = (page - 1) * per_page

        # Get conversations
        conversations, total = conversation_service.get_user_conversations(
            db, current_user.id, skip, per_page, knowledge_base_id
        )

        # Convert to response schemas
        conversation_responses = [
            ConversationResponse.model_validate(conv) for conv in conversations
        ]

        # Create pagination metadata
        pagination_meta = paginator_result(total, page, per_page)

        return paginate(pagination_meta, conversation_responses, "conversations")
    except Exception as e:
        logger.exception(e)
        raise e


@conversation_router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_conversation_detail(
    conversation_id: int,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    """
    Get conversation details with all messages.
    """
    try:
        conversation = conversation_service.get_conversation_by_id(
            db, conversation_id, current_user.id
        )
        return ConversationDetailResponse.model_validate(conversation)
    except Exception as e:
        logger.exception(e)
        raise e
