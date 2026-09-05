from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import AnalyticAccount, AnalyticType, User
from app.templating import templates

router = APIRouter(prefix="/analytic-accounts", tags=["analytic_accounts"])


@router.get("")
def list_analytic(request: Request, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    items = db.scalars(select(AnalyticAccount).order_by(AnalyticAccount.name)).all()
    return templates.TemplateResponse(request, "analytic_accounts/list.html", {
        "request": request, "user": user, "active": "analytic", "items": items,
    })


@router.get("/new")
def new_form(request: Request, user: User = Depends(require_role("admin", "accountant"))):
    return templates.TemplateResponse(request, "analytic_accounts/form.html", {
        "request": request, "user": user, "active": "analytic",
    })


@router.post("/new")
def create(request: Request, name: str = Form(...), type: str = Form(...),
            user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    if not name.strip():
        return templates.TemplateResponse(request, "analytic_accounts/form.html", {
            "request": request, "user": user, "active": "analytic", "error": "Name is required.",
        }, status_code=400)
    db.add(AnalyticAccount(name=name.strip(), type=AnalyticType(type)))
    db.commit()
    return RedirectResponse(url="/analytic-accounts?success=Analytic+account+created", status_code=303)
