from sqlalchemy.orm import relationship, Mapped
from sqlalchemy import (
    Text,
    func,
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
)

from .database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)

    # Use `default` to set the value in Python before insert,
    # `server_default` lets the DB set it during insert.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    first_name = Column(String(75), nullable=False)
    last_name = Column(String(75), nullable=True)
    email = Column(String(100), nullable=False)
    mobile_no = Column(String(15), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    # otp = Column(String(4), nullable=True)
    # otp_secret_key = Column(String(32), nullable=True)
    # is_otp_verified = Column(Boolean, default=False)
    # otp_count = Column(Integer, default=0)
    # resent_otp_count = Column(Integer, default=0)
    # last_otp_sent_at = Column(DateTime, nullable=True)
    # last_verified_at = Column(DateTime, nullable=True)
    # is_reset_resent_otp_count = Column(Boolean, nullable=True)

    is_email_verified = Column(Boolean, default=False)
    resent_email_count = Column(Integer, default=0)
    last_email_sent_at = Column(DateTime, nullable=True)

    encrypted_password = Column(Text, nullable=True)
    access_token = Column(Text, nullable=True)

    sign_in_count = Column(Integer, default=0)
    current_sign_in_ip = Column(String(50), nullable=True)
    last_sign_in_ip = Column(String(50), nullable=True)
    current_sign_in_at = Column(DateTime, nullable=True)
    last_sign_in_at = Column(DateTime, nullable=True)
    is_currently_logged_in = Column(Boolean, default=None)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), server_onupdate=func.now(), nullable=False
    )
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    role: Mapped[Role] = relationship("Role", back_populates="users")
    calendar_settings = relationship(
        "CalendarSettings", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    knowledge_bases = relationship("KnowledgeBase", back_populates="user", cascade="all, delete-orphan")
    datasources = relationship("Datasource", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class CalendarSettings(Base):
    """
    Stores user-specific calendar configuration including working hours,
    timezone, and calendar provider settings.
    """
    __tablename__ = "calendar_settings"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Calendar Provider
    calendar_provider = Column(String(50), nullable=False, default="google")  # google, outlook, etc.
    
    # Working Hours (24-hour format)
    work_hours_start = Column(Integer, nullable=False, default=9)  # 9 AM
    work_hours_end = Column(Integer, nullable=False, default=17)  # 5 PM
    
    # Timezone
    timezone = Column(String(100), nullable=False, default="Asia/Kolkata")
    
    # Working Days (JSON array of day numbers: 0=Sunday, 1=Monday, ..., 6=Saturday)
    working_days = Column(Text, nullable=False, default='[1,2,3,4,5]')  # Monday to Friday
    
    # Meeting Duration (in minutes)
    slot_duration_minutes = Column(Integer, nullable=False, default=30)
    
    # Calendar Integration Status
    is_calendar_connected = Column(Boolean, default=False)
    calendar_email = Column(String(100), nullable=True)  # Connected calendar email
    
    # Google Calendar Specific
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), server_onupdate=func.now(), nullable=False
    )
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="calendar_settings")


class KnowledgeBase(Base):
    """
    Stores user's knowledge bases (collections of documents).
    Each user can have multiple knowledge bases, but only one can be enabled for AI agent.
    """
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Knowledge Base Info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Status
    is_enabled = Column(Boolean, default=False, nullable=False)  # Only one can be enabled per user
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), server_onupdate=func.now(), nullable=False
    )
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="knowledge_bases")
    datasources: Mapped[list["Datasource"]] = relationship(
        "Datasource", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="knowledge_base"
    )


class Datasource(Base):
    """
    Stores metadata about user's uploaded files/documents.
    Does NOT store actual file content - only metadata for reference.
    """
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    
    # File Metadata
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, txt, md, docx, etc.
    file_size = Column(Integer, nullable=True)  # Size in bytes
    
    # Legacy field - keeping for backward compatibility, will be removed later
    collection_name = Column(String(255), nullable=True)
    
    # Processing Status
    status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed, cancelled
    task_id = Column(String(255), nullable=True)  # Celery task ID for tracking/cancellation
    
    # External References (if using vector DB or cloud storage)
    external_id = Column(String(255), nullable=True)  # ID in vector DB or cloud storage
    vector_db_collection = Column(String(255), nullable=True)  # Collection name in vector DB
    
    # Additional Metadata
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON array of tags
    
    # Processing Info
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), server_onupdate=func.now(), nullable=False
    )
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="datasources")
    knowledge_base: Mapped[KnowledgeBase] = relationship("KnowledgeBase", back_populates="datasources")


class Conversation(Base):
    """
    Stores user conversations from production widget.
    Each conversation represents a chat session with multiple messages.
    Belongs to user (not KB) so user can see all conversations across all KBs.
    KB ID is stored per message to allow switching KBs mid-conversation.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Session Info
    session_id = Column(String(255), nullable=False, index=True)  # Unique session identifier
    user_identifier = Column(String(255), nullable=True)  # Email, name, or anonymous ID from widget
    
    # Conversation Metadata
    first_message = Column(Text, nullable=True)  # Preview of first user message
    message_count = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, ended
    
    # Timestamps
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), server_onupdate=func.now(), nullable=False)
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """
    Stores individual messages within a conversation.
    Each message tracks which KB was used to generate the response,
    allowing KB switching mid-conversation.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True, unique=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)
    
    # Message Content
    role = Column(String(50), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    
    # Metadata
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    knowledge_base: Mapped[KnowledgeBase] = relationship("KnowledgeBase", back_populates="messages")
