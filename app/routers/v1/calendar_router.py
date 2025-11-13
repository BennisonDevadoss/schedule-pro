from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from config.models import User
from config.constants import USER_ROLES
from dependencies.auth import AuthenticateUser
from services import calendar_service
from config.logger import logger
from schemas.calendar_schema import (
    EventRequest,
    EventResponse,
    CalendarSettingsCreate,
    CalendarSettingsUpdate,
    CalendarSettingsResponse,
    GoogleCalendarAuthRequest,
    GoogleCalendarAuthResponse,
)

calendar_router = APIRouter(prefix="/calendar", tags=["Calendar"])


# @calendar_router.get("/auth")
# async def authenticate():
#     """
#     Authenticate your Google account once.
#     Opens browser for consent if needed.
#     """
#     try:
#         message = calendar_service.authenticate_user()
#         return {"message": message}
#     except Exception as e:
#         logger.exception(e)
#         raise e


@calendar_router.post("/create_event", response_model=EventResponse)
async def create_event(
    request: EventRequest,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
):
    """
    Create an event on your Google Calendar using your account.
    """
    try:
        event = calendar_service.create_event(
            db=db,
            user_id=current_user.id,
            summary=request.summary,
            start=request.start,
            timezone=request.timezone,
            attendees=request.attendees,
            location=request.location,
            description=request.description,
        )
        return EventResponse(
            event_id=event["event_id"],
            meet_link=event["meet_link"],
            event_link=event["event_link"],
        )
    except Exception as e:
        logger.exception(e)
        raise e


# Calendar Settings Endpoints
@calendar_router.get(
    "/settings",
    response_model=CalendarSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_calendar_settings(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> CalendarSettingsResponse:
    """
    Get calendar settings for the authenticated user.
    Creates default settings if none exist.
    """
    try:
        settings = calendar_service.get_or_create_calendar_settings(db, current_user.id)
        return settings
    except Exception as e:
        logger.exception(e)
        raise e


@calendar_router.post(
    "/settings",
    response_model=CalendarSettingsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_calendar_settings(
    settings: CalendarSettingsCreate,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> CalendarSettingsResponse:
    """
    Create calendar settings for the authenticated user.
    """
    try:
        created_settings = calendar_service.create_calendar_settings(
            db, current_user.id, settings
        )
        return created_settings
    except Exception as e:
        logger.exception(e)
        raise e


@calendar_router.put(
    "/settings",
    response_model=CalendarSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_calendar_settings(
    settings: CalendarSettingsUpdate,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> CalendarSettingsResponse:
    """
    Update calendar settings for the authenticated user.
    """
    try:
        updated_settings = calendar_service.update_calendar_settings(
            db, current_user.id, settings
        )
        return updated_settings
    except Exception as e:
        logger.exception(e)
        raise e


@calendar_router.get(
    "/google/auth-url",
    status_code=status.HTTP_200_OK,
)
async def get_google_auth_url(
    redirect_uri: str = Query(..., description="OAuth redirect URI"),
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))] = None,
) -> dict:
    """
    Get Google OAuth authorization URL for calendar integration.
    """
    try:
        auth_url = calendar_service.get_google_auth_url(redirect_uri, current_user.id)
        return {"auth_url": auth_url, "message": "Redirect user to this URL"}
    except Exception as e:
        logger.exception(e)
        raise e


@calendar_router.post(
    "/google/callback",
    response_model=GoogleCalendarAuthResponse,
    status_code=status.HTTP_200_OK,
)
async def google_oauth_callback(
    auth_request: GoogleCalendarAuthRequest,
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> GoogleCalendarAuthResponse:
    """
    Handle Google OAuth callback and store tokens.
    """
    try:
        settings = calendar_service.handle_google_oauth_callback(
            db, current_user.id, auth_request.code, auth_request.redirect_uri
        )
        return GoogleCalendarAuthResponse(
            message="Google Calendar connected successfully",
            calendar_email=settings.calendar_email,
            is_connected=settings.is_calendar_connected,
        )
    except Exception as e:
        logger.exception(e)
        raise e


@calendar_router.post(
    "/google/disconnect",
    response_model=CalendarSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def disconnect_google_calendar(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> CalendarSettingsResponse:
    """
    Disconnect Google Calendar for the authenticated user.
    """
    try:
        settings = calendar_service.disconnect_google_calendar(db, current_user.id)
        return settings
    except Exception as e:
        logger.exception(e)
        raise e


@calendar_router.delete(
    "/settings",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_calendar_settings(
    current_user: Annotated[User, Depends(AuthenticateUser([USER_ROLES.ADMIN]))],
    db: Session = Depends(get_db),
) -> None:
    """
    Delete calendar settings for the authenticated user.
    """
    try:
        calendar_service.delete_calendar_settings(db, current_user.id)
    except Exception as e:
        logger.exception(e)
        raise e
