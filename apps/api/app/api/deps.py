from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.settings import get_settings

DbSession = Annotated[Session, Depends(get_session)]


def current_user(request: Request, session: DbSession) -> User:
    email = request.session.get("email")
    if not email:
        raise HTTPException(401, "Niet ingelogd.")
    # De allowlist is leidend: wie eruit is gehaald, verliest direct toegang.
    role = get_settings().allowed_users().get(email)
    if not role:
        request.session.clear()
        raise HTTPException(403, "Geen toegang.")
    user = session.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(401, "Niet ingelogd.")
    if user.role != role:
        user.role = role
        session.commit()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Alleen voor admins.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
