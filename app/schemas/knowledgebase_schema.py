from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# Request Schemas
class KnowledgeBaseCreate(BaseModel):
    """Schema for creating a new knowledge base"""
    name: str = Field(..., min_length=1, max_length=100, description="Knowledge base name")
    description: Optional[str] = Field(None, description="Knowledge base description")
    is_enabled: bool = Field(default=False, description="Whether this knowledge base is enabled for AI agent")


class KnowledgeBaseUpdate(BaseModel):
    """Schema for updating a knowledge base"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Knowledge base name")
    description: Optional[str] = Field(None, description="Knowledge base description")


class KnowledgeBaseToggle(BaseModel):
    """Schema for toggling knowledge base enabled status"""
    is_enabled: bool = Field(..., description="Whether to enable or disable this knowledge base")


# Response Schemas
class KnowledgeBaseResponse(BaseModel):
    """Schema for knowledge base response"""
    id: int
    user_id: int
    name: str
    description: Optional[str]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    
    # Optional stats (can be added by service layer)
    file_count: Optional[int] = Field(default=0, description="Number of files in this knowledge base")
    total_size: Optional[int] = Field(default=0, description="Total size in bytes")
    
    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    """Schema for list of knowledge bases"""
    total: int = Field(..., description="Total number of knowledge bases")
    knowledge_bases: list[KnowledgeBaseResponse] = Field(..., description="List of knowledge bases")


class KnowledgeBaseStatsResponse(BaseModel):
    """Schema for knowledge base statistics"""
    total_knowledge_bases: int
    enabled_knowledge_base: Optional[KnowledgeBaseResponse] = None
    total_files: int
    total_size_bytes: int
