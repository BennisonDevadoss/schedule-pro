from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class MessageResponse(BaseModel):
    """Schema for message response"""
    id: int
    conversation_id: int
    knowledge_base_id: Optional[int]  # Track which KB was used for this message
    role: str  # user, assistant
    content: str
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Schema for conversation response"""
    id: int
    user_id: int
    session_id: str
    user_identifier: Optional[str]
    first_message: Optional[str]
    message_count: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    """Schema for conversation with messages"""
    id: int
    user_id: int
    session_id: str
    user_identifier: Optional[str]
    first_message: Optional[str]
    message_count: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    messages: list[MessageResponse]
    
    model_config = ConfigDict(from_attributes=True)


class TestChatRequest(BaseModel):
    """Schema for test chat request"""
    message: str
    session_id: Optional[str] = None  # For continuing conversation


class TestChatResponse(BaseModel):
    """Schema for test chat response"""
    message: str
    session_id: str
