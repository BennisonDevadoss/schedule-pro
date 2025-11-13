from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


class CrawlParams(BaseModel):
    """DEPRECATED: Use CrawlUrlsRequest instead"""
    knowledge_base_id: int = Field(..., description="Knowledge base ID")
    urls: list[HttpUrl]


class CrawlUrlsRequest(BaseModel):
    """Enterprise standard: URLs only, KB ID from path"""
    urls: list[HttpUrl] = Field(..., description="List of URLs to crawl")


class CrawlResponse(BaseModel):
    message: str
    task_id: str


class FileUploadResponse(BaseModel):
    message: str
    task_id: str


class TempFileUploadResponse(BaseModel):
    message: str


class TaskStatusResponse(BaseModel):
    status: str
    task_id: str
    result: str | None = None


# New Datasource Schemas for User File Metadata
class DatasourceBase(BaseModel):
    """Base schema for datasource"""
    file_name: str = Field(..., description="Name of the file")
    file_type: str = Field(..., description="File type/extension (pdf, txt, md, etc.)")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    knowledge_base_id: int = Field(..., description="Knowledge base ID")
    collection_name: Optional[str] = Field(None, description="Collection/category name (deprecated)")
    description: Optional[str] = Field(None, description="File description")
    tags: Optional[str] = Field(None, description="JSON array of tags")


class DatasourceCreate(DatasourceBase):
    """Schema for creating a datasource entry"""
    external_id: Optional[str] = Field(None, description="External ID (vector DB, cloud storage)")
    vector_db_collection: Optional[str] = Field(None, description="Vector DB collection name")


class DatasourceUpdate(BaseModel):
    """Schema for updating datasource (all fields optional)"""
    file_name: Optional[str] = None
    knowledge_base_id: Optional[int] = None
    collection_name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = Field(None, description="Status: pending, processing, completed, failed")


class DatasourceResponse(DatasourceBase):
    """Schema for datasource response"""
    id: int
    user_id: int
    knowledge_base_id: int
    status: str
    external_id: Optional[str] = None
    vector_db_collection: Optional[str] = None
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasourceListResponse(BaseModel):
    """Schema for list of datasources"""
    total: int
    datasources: list[DatasourceResponse]


class DatasourceStats(BaseModel):
    """Schema for datasource statistics"""
    total: int
    completed: int
    processing: int
    failed: int
    total_size_bytes: int
