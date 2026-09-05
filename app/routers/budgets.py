from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import AnalyticAccount, Budget, User
from app.services.reports import budget_report
from app.templating import templates
from app.validators import ValidationError

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("")
def list_budgets(request: Request, user: User = Depends(require_role("admin", "accountant")),
                  db: Session = Depends(get_db)):
    rows = budget_report(db)
    return templates.TemplateResponse("budgets/list.html", {
        "request": request, "user": user, "active": "budgets", "rows": rows,
    })


@router.get("/new")
def new_budget_form(request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    analytic_accounts = db.scalars(select(AnalyticAccount).order_by(AnalyticAccount.name)).all()
    return templates.TemplateResponse("budgets/form.html", {
        "request": request, "user": user, "active": "budgets", "analytic_accounts": analytic_accounts,
    })


@router.post("/new")
def create_budget(
    request: Request,
    name: str = Form(...),
    period_start: str = Form(...),
    period_end: str = Form(...),
    responsible_person: str = Form(...),
    planned_amount: float = Form(...),
    analytic_account_id: int = Form(...),
    user: User = Depends(require_role("admin", "accountant")),
    db: Session = Depends(get_db),
):
    try:
        if not name.strip():
            raise ValidationError("Budget name is required.")
        if planned_amount < 0:
            raise ValidationError("Planned amount cannot be negative.")
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        if end < start:
            raise ValidationError("Period end must be after period start.")
        budget = Budget(
            name=name.strip(), period_start=start, period_end=end,
            responsible_person=responsible_person.strip(), planned_amount=planned_amount,
            analytic_account_id=analytic_account_id,
        )
        db.add(budget)
        db.commit()
    except ValidationError as e:
        analytic_accounts = db.scalars(select(AnalyticAccount).order_by(AnalyticAccount.name)).all()
        return templates.TemplateResponse("budgets/form.html", {
            "request": request, "user": user, "active": "budgets",
            "analytic_accounts": analytic_accounts, "error": e.message,
        }, status_code=400)
    return RedirectResponse(url=f"/budgets/{budget.id}?success=Budget+created", status_code=303)


@router.get("/{budget_id}")
def budget_detail(budget_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if not budget:
        return RedirectResponse(url="/budgets?error=Budget+not+found", status_code=303)
    row = next((r for r in budget_report(db) if r["budget"].id == budget.id), None)
    return templates.TemplateResponse("budgets/detail.html", {
        "request": request, "user": user, "active": "budgets", "budget": budget, "row": row,
    })
