from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, SessionLocal, engine
from app.seed import seed_if_empty

app = FastAPI(title="Urban Furniture Accounting System")
app.add_middleware(SessionMiddleware, secret_key="urban-furniture-hackathon-demo-secret")

import os
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return RedirectResponse(url="/?error=You+do+not+have+permission+to+do+that", status_code=303)


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
