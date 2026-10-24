from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api import assets, auth, catalog, posts
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    if not settings.session_secret:
        raise RuntimeError("SESSION_SECRET ontbreekt in .env.")
    if settings.environment == "production" and settings.auth_mode == "dev":
        raise RuntimeError("AUTH_MODE=dev is niet toegestaan in productie.")

    app = FastAPI(
        title="Flow Social Generator API", docs_url="/api/docs", openapi_url="/api/openapi.json"
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="flow_social_session",
        same_site="lax",
        https_only=settings.public_url.startswith("https://"),
        max_age=60 * 60 * 24 * 14,
    )
    for module in (auth, catalog, assets, posts):
        app.include_router(module.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
