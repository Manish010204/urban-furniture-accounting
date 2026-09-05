import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import IS_PRODUCTION, SECRET_KEY, SESSION_MAX_AGE_SECONDS
from app.database import Base, SessionLocal, engine
from app.seed import seed_if_empty
from app.templating import templates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    logger.info("Application startup complete (environment=%s)", "production" if IS_PRODUCTION else "development")
    yield


app = FastAPI(title="Urban Furniture Accounting System", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="strict",
    https_only=IS_PRODUCTION,
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def block_cross_origin_writes(request: Request, call_next):
    """Lightweight CSRF defense: a same-origin session cookie (SameSite=Strict,
    set above) already stops the cookie being sent on a cross-site request; this
    adds a second, independent check by rejecting any state-changing request
    whose Origin/Referer header names a different host than this app, so a
    forged form on another site can't ride the user's session even if some
    browser/proxy ever fails to honor SameSite."""
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            origin_host = urlparse(origin).netloc
            if origin_host and origin_host != request.url.netloc:
                logger.warning("Blocked cross-origin %s to %s from Origin/Referer %s",
                                request.method, request.url.path, origin)
                return RedirectResponse(url="/?error=Request+blocked+for+your+security.+Please+try+again.",
                                         status_code=303)
    return await call_next(request)


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return RedirectResponse(url="/?error=You+do+not+have+permission+to+do+that", status_code=303)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(request, "errors/error.html", {
        "request": request, "user": None, "code": 404,
        "heading": "Page not found", "message": "The page you're looking for doesn't exist.",
    }, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.exception("Unhandled server error on %s %s", request.method, request.url.path, exc_info=exc)
    return templates.TemplateResponse(request, "errors/error.html", {
        "request": request, "user": None, "code": 500,
        "heading": "Something went wrong", "message": "An unexpected error occurred. Please try again.",
    }, status_code=500)


from app.routers import (  # noqa: E402
    accounts,
    analytic_accounts,
    auth,
    budgets,
    contacts,
    dashboard,
    journal_entries,
    journals,
    payments,
    products,
    purchases,
    reports,
    sales,
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(contacts.router)
app.include_router(products.router)
app.include_router(accounts.router)
app.include_router(journals.router)
app.include_router(journal_entries.router)
app.include_router(analytic_accounts.router)
app.include_router(budgets.router)
app.include_router(purchases.router)
app.include_router(sales.router)
app.include_router(payments.router)
app.include_router(reports.router)
