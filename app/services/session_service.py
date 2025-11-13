from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config.models import User
from dependencies.auth import create_access_token
from utils.password_utils import verify_password
from schemas.session_schema import UserSigninParams
from schemas.calendar_schema import CalendarSettingsCreate
from exceptions.custom_errors import UnauthorizedException
from services import calendar_service, knowledgebase_service


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()


def signin_user(db: Session, params: UserSigninParams) -> tuple[User, str]:
    user = get_user_by_email(db, params.email)
    if not user:
        raise UnauthorizedException("Invalid username or password")
    if not user.is_email_verified:
        UnauthorizedException("Please accept invitation in your email")

    if not verify_password(params.password, user.encrypted_password):
        raise UnauthorizedException("Incorrect username or password")

    access_token = create_access_token(
        data={"email": user.email, "timestamp": str(datetime.now(timezone.utc))}
    )

    user.access_token = access_token
    user.is_currently_logged_in = True
    user.last_sign_in_at = user.current_sign_in_at
    user.current_sign_in_at = datetime.now(timezone.utc)
    user.last_sign_in_ip = user.current_sign_in_ip
    user.current_sign_in_ip = params.ip_address
    user.sign_in_count += 1
    db.commit()

    # Create calendar settings if they don't exist
    # This ensures every user has calendar settings after login
    try:
        existing_settings = calendar_service.get_calendar_settings_by_user_id(db, user.id)
        if not existing_settings:
            # Create default calendar settings
            default_settings = CalendarSettingsCreate()
            calendar_service.create_calendar_settings(db, user.id, default_settings)
    except Exception as e:
        # If calendar settings creation fails, rollback and fail the login
        db.rollback()
        raise Exception(f"Failed to initialize calendar settings: {str(e)}")
    
    # Create default knowledge base if user doesn't have any
    # This ensures every user has at least one knowledge base
    try:
        knowledgebase_service.get_or_create_default_knowledge_base(db, user.id)
    except Exception as e:
        # If knowledge base creation fails, rollback and fail the login
        db.rollback()
        raise Exception(f"Failed to initialize knowledge base: {str(e)}")

    return user, access_token
