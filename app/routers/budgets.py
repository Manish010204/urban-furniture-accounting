from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import AnalyticAccount, Budget, BudgetLine, BudgetStatus, Contact, User
from app.services.reports import budget_report
from app.templating import templates
from app.validators import ValidationError

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("")
def list_budgets(request: Request, user: User = Depends(require_role("admin", "accountant")),
                  db: Session = Depends(get_db)):
    rows = budget_report(db)
    return templates.TemplateResponse(request, "budgets/list.html", {
        "request": request, "user": user, "active": "budgets", "rows": rows,
    })


@router.get("/new")
def new_budget_form(request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    analytic_accounts = db.scalars(select(AnalyticAccount).order_by(AnalyticAccount.name)).all()
    contacts = db.scalars(select(Contact).where(Contact.is_archived == False).order_by(Contact.name)).all()  # noqa: E712
    return templates.TemplateResponse(request, "budgets/form.html", {
        "request": request, "user": user, "active": "budgets",
        "analytic_accounts": analytic_accounts, "contacts": contacts,
    })


@router.post("/new")
async def create_budget(request: Request, user: User = Depends(require_role("admin", "accountant")),
                         db: Session = Depends(get_db)):
    form = await request.form()
    name = form.get("name", "")
    period_start = form.get("period_start")
    period_end = form.get("period_end")
    responsible_person = form.get("responsible_person", "")
    analytic_account_ids = form.getlist("analytic_account_id")
    committed_amounts = form.getlist("committed_amount")

    def render_error(message):
        analytic_accounts = db.scalars(select(AnalyticAccount).order_by(AnalyticAccount.name)).all()
        contacts = db.scalars(select(Contact).where(Contact.is_archived == False).order_by(Contact.name)).all()  # noqa: E712
        return templates.TemplateResponse(request, "budgets/form.html", {
            "request": request, "user": user, "active": "budgets",
            "analytic_accounts": analytic_accounts, "contacts": contacts, "error": message,
        }, status_code=400)

    try:
        if not name.strip():
            raise ValidationError("Budget name is required.")
        if not responsible_person.strip():
            raise ValidationError("Responsible person is required.")
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        if end < start:
            raise ValidationError("Period end must be after period start.")

        lines = []
        for aid, amount in zip(analytic_account_ids, committed_amounts):
            if not aid:
                continue
            amount_f = Decimal(amount or "0")
            if amount_f < 0:
                raise ValidationError("Committed amount cannot be negative.")
            lines.append(BudgetLine(analytic_account_id=int(aid), committed_amount=amount_f))
        if not lines:
            raise ValidationError("Add at least one analytic account line.")

        budget = Budget(name=name.strip(), period_start=start, period_end=end,
                         responsible_person=responsible_person.strip(), status=BudgetStatus.draft)
        budget.lines = lines
        db.add(budget)
        db.commit()
    except ValidationError as e:
        return render_error(e.message)
    return RedirectResponse(url=f"/budgets/{budget.id}?success=Budget+created", status_code=303)


@router.get("/{budget_id}")
def budget_detail(budget_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if not budget:
        return RedirectResponse(url="/budgets?error=Budget+not+found", status_code=303)
    row = next((r for r in budget_report(db) if r["budget"].id == budget.id), None)
    revised_by = db.scalar(select(Budget).where(Budget.revises_budget_id == budget.id))
    return templates.TemplateResponse(request, "budgets/detail.html", {
        "request": request, "user": user, "active": "budgets", "budget": budget, "row": row,
        "revised_by": revised_by,
    })


@router.post("/{budget_id}/confirm")
def confirm_budget(budget_id: int, user: User = Depends(require_role("admin", "accountant")),
                    db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if not budget:
        return RedirectResponse(url="/budgets?error=Budget+not+found", status_code=303)
    if budget.status != BudgetStatus.draft:
        return RedirectResponse(url=f"/budgets/{budget.id}?error=Only+draft+budgets+can+be+confirmed", status_code=303)
    budget.status = BudgetStatus.confirmed
    db.commit()
    return RedirectResponse(url=f"/budgets/{budget.id}?success=Budget+confirmed", status_code=303)


@router.post("/{budget_id}/cancel")
def cancel_budget(budget_id: int, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if not budget:
        return RedirectResponse(url="/budgets?error=Budget+not+found", status_code=303)
    if budget.status not in (BudgetStatus.draft, BudgetStatus.confirmed):
        return RedirectResponse(url=f"/budgets/{budget.id}?error=This+budget+cannot+be+cancelled", status_code=303)
    budget.status = BudgetStatus.cancelled
    db.commit()
    return RedirectResponse(url=f"/budgets/{budget.id}?success=Budget+cancelled", status_code=303)


@router.get("/{budget_id}/revise")
def revise_budget_form(budget_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                        db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if not budget:
        return RedirectResponse(url="/budgets?error=Budget+not+found", status_code=303)
    if budget.status != BudgetStatus.confirmed:
        return RedirectResponse(url=f"/budgets/{budget.id}?error=Only+confirmed+budgets+can+be+revised", status_code=303)
    suggested_name = budget.name if "Revised" in budget.name else f"{budget.name} Revised"
    return templates.TemplateResponse(request, "budgets/revise.html", {
        "request": request, "user": user, "active": "budgets", "budget": budget, "suggested_name": suggested_name,
    })


@router.post("/{budget_id}/revise")
async def revise_budget(budget_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                         db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if not budget:
        return RedirectResponse(url="/budgets?error=Budget+not+found", status_code=303)
    if budget.status != BudgetStatus.confirmed:
        return RedirectResponse(url=f"/budgets/{budget.id}?error=Only+confirmed+budgets+can+be+revised", status_code=303)

    form = await request.form()
    new_name = form.get("name", "").strip() or f"{budget.name} Revised"
    line_ids = form.getlist("line_id")
    committed_amounts = form.getlist("committed_amount")

    new_lines = []
    for original_line in budget.lines:
        for line_id, amount in zip(line_ids, committed_amounts):
            if int(line_id) == original_line.id:
                new_lines.append(BudgetLine(analytic_account_id=original_line.analytic_account_id,
                                             committed_amount=Decimal(amount or "0")))
                break

    revised_budget = Budget(
        name=new_name, period_start=budget.period_start, period_end=budget.period_end,
        responsible_person=budget.responsible_person, status=BudgetStatus.confirmed,
        revises_budget_id=budget.id,
    )
    revised_budget.lines = new_lines
    db.add(revised_budget)
    budget.status = BudgetStatus.revised
    db.commit()
    return RedirectResponse(url=f"/budgets/{revised_budget.id}?success=Budget+revised", status_code=303)
