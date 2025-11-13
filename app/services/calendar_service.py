import uuid
from typing import Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from config.settings import SETTINGS
from config.models import CalendarSettings
from schemas.calendar_schema import (
    CalendarSettingsCreate,
    CalendarSettingsUpdate,
)
from exceptions.custom_errors import (
    NotFoundException,
    ConflictException,
    BadRequestException,
    UnauthorizedException,
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


# Calendar Settings Functions
def get_calendar_settings_by_user_id(
    db: Session, user_id: int
) -> Optional[CalendarSettings]:
    """Get calendar settings for a specific user"""
    return (
        db.query(CalendarSettings)
        .filter(
            CalendarSettings.user_id == user_id,
            CalendarSettings.deleted_at.is_(None),
        )
        .first()
    )


def create_calendar_settings(
    db: Session, user_id: int, settings: CalendarSettingsCreate
) -> CalendarSettings:
    """Create calendar settings for a user"""
    # Check if settings already exist
    existing = get_calendar_settings_by_user_id(db, user_id)
    if existing:
        raise BadRequestException("Calendar settings already exist for this user")

    calendar_settings = CalendarSettings(
        user_id=user_id,
        calendar_provider=settings.calendar_provider,
        work_hours_start=settings.work_hours_start,
        work_hours_end=settings.work_hours_end,
        timezone=settings.timezone,
        working_days=settings.working_days,
        slot_duration_minutes=settings.slot_duration_minutes,
    )

    db.add(calendar_settings)
    db.commit()
    db.refresh(calendar_settings)
    return calendar_settings


def update_calendar_settings(
    db: Session, user_id: int, settings: CalendarSettingsUpdate
) -> CalendarSettings:
    """Update calendar settings for a user"""
    calendar_settings = get_calendar_settings_by_user_id(db, user_id)
    if not calendar_settings:
        raise NotFoundException("Calendar settings not found for this user")

    # Update only provided fields
    update_data = settings.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(calendar_settings, field, value)

    db.commit()
    db.refresh(calendar_settings)
    return calendar_settings


def get_or_create_calendar_settings(db: Session, user_id: int) -> CalendarSettings:
    """Get existing calendar settings or create default ones"""
    settings = get_calendar_settings_by_user_id(db, user_id)
    if not settings:
        # Create default settings
        default_settings = CalendarSettingsCreate()
        settings = create_calendar_settings(db, user_id, default_settings)
    return settings


def get_google_oauth_flow(redirect_uri: str) -> Flow:
    """Create Google OAuth flow"""
    flow = Flow.from_client_secrets_file(
        "./creds/credentials.json",
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def get_google_auth_url(redirect_uri: str, user_id: int) -> str:
    """Generate Google OAuth authorization URL"""
    flow = get_google_oauth_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Force consent to get refresh token
        state=str(user_id),  # Pass user_id in state for callback
    )
    return authorization_url


def handle_google_oauth_callback(
    db: Session, user_id: int, code: str, redirect_uri: str
) -> CalendarSettings:
    """
    Handle Google OAuth callback and store tokens in database.
    """
    # Get or create calendar settings
    calendar_settings = get_or_create_calendar_settings(db, user_id)

    # Exchange code for tokens
    flow = get_google_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)

    credentials = flow.credentials

    # Get user's calendar email
    service = build("calendar", "v3", credentials=credentials)
    calendar = service.calendars().get(calendarId="primary").execute()
    calendar_email = calendar.get("id")

    # Store tokens in database
    calendar_settings.google_access_token = credentials.token
    calendar_settings.google_refresh_token = credentials.refresh_token
    calendar_settings.google_token_expiry = credentials.expiry
    calendar_settings.is_calendar_connected = True
    calendar_settings.calendar_email = calendar_email

    db.commit()
    db.refresh(calendar_settings)

    return calendar_settings


def get_google_credentials(db: Session, user_id: int) -> Credentials:
    """
    Get Google Calendar credentials for a user from database.
    Refreshes token if expired.
    """
    calendar_settings = get_calendar_settings_by_user_id(db, user_id)

    if not calendar_settings or not calendar_settings.is_calendar_connected:
        raise UnauthorizedException(
            "Google Calendar not connected. Please authenticate first."
        )

    # Create credentials object from stored tokens
    credentials = Credentials(
        token=calendar_settings.google_access_token,
        refresh_token=calendar_settings.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=SETTINGS.GOOGLE_CLIENT_ID,
        client_secret=SETTINGS.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )

    # Refresh token if expired
    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request

        credentials.refresh(Request())

        # Update tokens in database
        calendar_settings.google_access_token = credentials.token
        calendar_settings.google_token_expiry = credentials.expiry
        db.commit()

    return credentials


def disconnect_google_calendar(db: Session, user_id: int) -> CalendarSettings:
    """Disconnect Google Calendar for a user"""
    calendar_settings = get_calendar_settings_by_user_id(db, user_id)

    if not calendar_settings:
        raise NotFoundException("Calendar settings not found")

    # Clear Google Calendar tokens
    calendar_settings.google_access_token = None
    calendar_settings.google_refresh_token = None
    calendar_settings.google_token_expiry = None
    calendar_settings.is_calendar_connected = False
    calendar_settings.calendar_email = None

    db.commit()
    db.refresh(calendar_settings)

    return calendar_settings


def delete_calendar_settings(db: Session, user_id: int) -> None:
    """Soft delete calendar settings"""
    calendar_settings = get_calendar_settings_by_user_id(db, user_id)

    if not calendar_settings:
        raise NotFoundException("Calendar settings not found")

    calendar_settings.deleted_at = datetime.now()
    db.commit()


def get_calendar_service(db: Session, user_id: int) -> Any:
    """
    Get Google Calendar service for a specific user using their stored credentials.
    """
    credentials = get_google_credentials(db, user_id)
    service = build("calendar", "v3", credentials=credentials)
    return service


def is_time_slot_free_for_me(
    service: Any,
    start: datetime,
    end: datetime,
    organizer_email: str,  # oragnizer_email should be mine
) -> bool:
    """
    Checks if the primary calendar is free for events created by the authenticated user.
    Returns True if free, False if a conflicting event exists.
    """
    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        # Filter only events created by this user
        my_events = [
            e for e in events if e.get("creator", {}).get("email") == organizer_email
        ]

        return len(my_events) == 0  # True if no events created by me in this range

    except HttpError as e:
        raise e


def validate_event_slot(service: Any, start: datetime, end: datetime) -> None:
    """Validates that the event start time is within working hours and computes end time."""
    # Define working hours
    work_start = start.replace(
        hour=SETTINGS.CALENDAR_WORKING_HOURS_START, minute=0, second=0, microsecond=0
    )
    work_end = start.replace(
        hour=SETTINGS.CALENDAR_WORKING_HOURS_END, minute=0, second=0, microsecond=0
    )

    # Check working hours
    if not (work_start <= start < work_end) or not (work_start < end <= work_end):
        raise BadRequestException(
            f"Event must be within working hours: "
            f"{SETTINGS.CALENDAR_WORKING_HOURS_START}:00 - "
            f"{SETTINGS.CALENDAR_WORKING_HOURS_END}:00"
        )

    # Check for conflicts in the organizer's calendar
    if not is_time_slot_free_for_me(
        service, start, end, SETTINGS.CALENDAR_ORGANIZER_EMAIL
    ):
        raise ConflictException(
            "The requested time slot overlaps with an existing event"
        )


def create_event(
    db: Session,
    user_id: int,
    summary: str,
    start: datetime,
    timezone: str | None = "Asia/Kolkata",
    attendees: list[str] | None = None,
    description: str | None = None,
    location: str | None = None,
    reminders: list[dict[str, Any]] | None = None,
) -> dict:
    """
    Creates an event on Google Calendar with Google Meet link and optional details.
    End time is automatically calculated using slot duration and validated.
    """
    service = get_calendar_service(db, user_id)

    end = start + timedelta(minutes=SETTINGS.CALENDAR_SLOT_DURATION_MINUTES)
    validate_event_slot(service, start, end)

    event = {
        "summary": summary,
        "location": location or "",
        "description": description or "",
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
        "conferenceData": {  # Google Meet setup
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]

    if reminders:
        event["reminders"] = {
            "useDefault": False,
            "overrides": reminders,  # e.g., [{"method": "email", "minutes": 30}]
        }

    created_event = (
        service.events()
        .insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",
            conferenceDataVersion=1,  # Required for Meet link
        )
        .execute()
    )

    return {
        "event_link": created_event.get("htmlLink"),
        "meet_link": created_event.get("conferenceData", {})
        .get("entryPoints", [{}])[0]
        .get("uri"),
        "event_id": created_event.get("id"),
    }


# uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib
# https://developers.google.com/workspace/calendar/api/v3/reference/events?authuser=1#resource-representations
