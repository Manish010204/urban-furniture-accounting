from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import User
from app.services import reports as reports_service
from app.templating import templates

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def reports_index(request: Request, user: User = Depends(require_role("admin", "accountant"))):
    return templates.TemplateResponse(request, "reports/index.html", {
        "request": request, "user": user, "active": "reports",
    })


@router.get("/balance-sheet")
def balance_sheet_report(request: Request, as_of: str = "", user: User = Depends(require_role("admin", "accountant")),
                          db: Session = Depends(get_db)):
    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    data = reports_service.balance_sheet(db, as_of=as_of_date)
    return templates.TemplateResponse(request, "reports/balance_sheet.html", {
        "request": request, "user": user, "active": "reports", "data": data, "as_of": as_of_date.isoformat(),
    })


@router.get("/profit-loss")
def profit_loss_report(request: Request, since: str = "", as_of: str = "",
                        user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    since_date = date.fromisoformat(since) if since else None
    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    data = reports_service.profit_and_loss(db, as_of=as_of_date, since=since_date)
    return templates.TemplateResponse(request, "reports/profit_loss.html", {
        "request": request, "user": user, "active": "reports", "data": data,
        "since": since_date.isoformat() if since_date else "", "as_of": as_of_date.isoformat(),
    })


@router.get("/budget")
def budget_report_page(request: Request, user: User = Depends(require_role("admin", "accountant")),
                        db: Session = Depends(get_db)):
    rows = reports_service.budget_report(db)
    return templates.TemplateResponse(request, "reports/budget.html", {
        "request": request, "user": user, "active": "reports", "rows": rows,
    })
