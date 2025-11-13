from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field, field_validator


class EventRequest(BaseModel):
    summary: str
    start: datetime
    end: datetime | None  # NOTE: end is not used.
    timezone: str | None = Field(default="Asia/Kolkata")
    attendees: list[str] | None = None
    description: str | None = None
    location: str | None = None


class EventResponse(BaseModel):
    event_id: str
    meet_link: HttpUrl | None = None
    event_link: HttpUrl


# Calendar Settings Schemas
class CalendarSettingsBase(BaseModel):
    """Base schema for calendar settings"""
    calendar_provider: str = Field(default="google", description="Calendar provider (google, outlook, etc.)")
    work_hours_start: int = Field(default=9, ge=0, le=23, description="Work start hour (0-23)")
    work_hours_end: int = Field(default=17, ge=0, le=23, description="Work end hour (0-23)")
    timezone: str = Field(default="Asia/Kolkata", description="User timezone")
    working_days: str = Field(default='[1,2,3,4,5]', description="JSON array of working days (0=Sun, 6=Sat)")
    slot_duration_minutes: int = Field(default=30, ge=15, le=240, description="Meeting slot duration in minutes")

    @field_validator('work_hours_end')
    @classmethod
    def validate_work_hours(cls, v, info):
        """Ensure work_hours_end is after work_hours_start"""
        if 'work_hours_start' in info.data and v <= info.data['work_hours_start']:
            raise ValueError('work_hours_end must be greater than work_hours_start')
        return v


class CalendarSettingsCreate(CalendarSettingsBase):
    """Schema for creating calendar settings"""
    pass


class CalendarSettingsUpdate(BaseModel):
    """Schema for updating calendar settings (all fields optional)"""
    calendar_provider: Optional[str] = None
    work_hours_start: Optional[int] = Field(None, ge=0, le=23)
    work_hours_end: Optional[int] = Field(None, ge=0, le=23)
    timezone: Optional[str] = None
    working_days: Optional[str] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=15, le=240)


class CalendarSettingsResponse(CalendarSettingsBase):
    """Schema for calendar settings response"""
    id: int
    user_id: int
    is_calendar_connected: bool
    calendar_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GoogleCalendarAuthRequest(BaseModel):
    """Schema for Google Calendar OAuth callback"""
    code: str = Field(..., description="OAuth authorization code")
    redirect_uri: str = Field(..., description="OAuth redirect URI")


class GoogleCalendarAuthResponse(BaseModel):
    """Schema for Google Calendar auth response"""
    message: str
    calendar_email: str
    is_connected: bool
