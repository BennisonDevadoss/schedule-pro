from typing import Annotated
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from sqlalchemy.orm import Session
from jwt.exceptions import InvalidTokenError
from fastapi.security import OAuth2PasswordBearer

from config.models import User
from config.database import get_db
from config.settings import SETTINGS
from config.constants import USER_ROLES
from services.user_service import get_user_by_email
from exceptions.custom_errors import UnauthorizedException, ForbiddenException


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, SETTINGS.JWT_SECRET_KEY, algorithm=SETTINGS.ALGORITHM
    )
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> User:
    if not token:
        raise UnauthorizedException("You need to sign-in to access this page")
    try:
        payload: dict = jwt.decode(
            token, SETTINGS.JWT_SECRET_KEY, algorithms=[SETTINGS.ALGORITHM]
        )
        email = payload.get("email")
        if email is None:
            raise UnauthorizedException("Session has expired")
    except InvalidTokenError:
        raise UnauthorizedException("Session has expired")
    try:
        user = get_user_by_email(email, db)
        if user.access_token != token:
            raise UnauthorizedException("Session has expired")
    except Exception:
        raise UnauthorizedException("Session has expired")
    return user


# https://stackademic.com/blog/fastapi-role-base-access-control-with-jwt-9fa2922a088c
class AuthenticateUser:
    def __init__(self, allowed_roles: list[USER_ROLES]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role.name not in self.allowed_roles:
            raise ForbiddenException(
                "You do not have the necessary permissions to access this resource."
            )
        return user
