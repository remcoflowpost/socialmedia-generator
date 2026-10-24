"""Login via Google Workspace OAuth met een allowlist uit .env.

AUTH_MODE=dev staat een login zonder Google toe, maar alleen in development en alleen
voor adressen op de allowlist.
"""

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()
_settings = get_settings()
if _settings.google_client_id:
    oauth.register(
        name="google",
        client_id=_settings.google_client_id,
        client_secret=_settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _login(request: Request, session: DbSession, email: str, name: str) -> User:
    email = email.lower()
    role = get_settings().allowed_users().get(email)
    if not role:
        raise HTTPException(403, "Dit e-mailadres staat niet op de allowlist.")
    user = session.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, name=name or email.split("@")[0], role=role)
        session.add(user)
    user.role = role
    session.commit()
    request.session["email"] = email
    return user


@router.get("/config")
def auth_config() -> dict:
    settings = get_settings()
    dev = settings.auth_mode == "dev" and settings.environment == "development"
    return {
        "mode": "dev" if dev else "google",
        "devUsers": list(settings.allowed_users()) if dev else [],
    }


@router.get("/login")
async def login(request: Request):
    if "google" not in oauth._clients:  # noqa: SLF001
        raise HTTPException(500, "Google OAuth is niet geconfigureerd (GOOGLE_CLIENT_ID).")
    redirect_uri = f"{get_settings().public_url}/api/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, session: DbSession):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(400, f"Inloggen mislukt: {error.error}") from error
    info = token.get("userinfo") or {}
    if not info.get("email_verified"):
        raise HTTPException(403, "E-mailadres is niet geverifieerd bij Google.")
    _login(request, session, info["email"], info.get("name", ""))
    return RedirectResponse(get_settings().public_url + "/")


@router.post("/dev-login")
def dev_login(request: Request, session: DbSession, body: dict) -> dict:
    settings = get_settings()
    if settings.auth_mode != "dev" or settings.environment != "development":
        raise HTTPException(404)
    user = _login(request, session, body.get("email", ""), "")
    return {"email": user.email, "role": user.role}


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}
