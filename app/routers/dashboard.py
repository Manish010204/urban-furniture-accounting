from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import (
    Budget,
    BudgetStatus,
    CustomerInvoice,
    POStatus,
    PurchaseOrder,
    SalesOrder,
    SOStatus,
    User,
    VendorBill,
)
from app.services import accounting, reports
from app.templating import templates

router = APIRouter()


def _status_counts(db: Session, model, status_col, confirmed_statuses, draft_status, cancelled_status):
    all_count = db.scalar(select(func.count()).select_from(model).where(status_col != cancelled_status)) or 0
    confirmed_count = db.scalar(
        select(func.count()).select_from(model).where(status_col.in_(confirmed_statuses))
    ) or 0
    draft_count = db.scalar(select(func.count()).select_from(model).where(status_col == draft_status)) or 0
    return {"all": all_count, "confirmed": confirmed_count, "draft": draft_count}


@router.get("/")
def home(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    if user.role.value == "contact":
        return _contact_home(request, user, db)

    pnl = reports.profit_and_loss(db)
    cash = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_CASH))
    bank = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_BANK))
    debtors = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_DEBTORS))
    creditors = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_CREDITORS))

    total_sales = pnl["total_income"]
    total_purchases = next((r["balance"] for r in pnl["expenses"]
                             if r["account"].name == accounting.ACCOUNT_PURCHASES_EXPENSE), 0)

    recent_invoices = db.scalars(select(CustomerInvoice).order_by(CustomerInvoice.id.desc()).limit(5)).all()
    recent_bills = db.scalars(select(VendorBill).order_by(VendorBill.id.desc()).limit(5)).all()

    sales_counts = _status_counts(db, SalesOrder, SalesOrder.status,
                                   (SOStatus.confirmed, SOStatus.invoiced), SOStatus.draft, SOStatus.cancelled)
    purchase_counts = _status_counts(db, PurchaseOrder, PurchaseOrder.status,
                                      (POStatus.confirmed, POStatus.billed), POStatus.draft, POStatus.cancelled)
    budget_counts = _status_counts(db, Budget, Budget.status,
                                    (BudgetStatus.confirmed, BudgetStatus.revised), BudgetStatus.draft,
                                    BudgetStatus.cancelled)

    return templates.TemplateResponse(request, "dashboard/index.html", {
        "request": request, "user": user, "active": "dashboard",
        "total_sales": total_sales, "total_purchases": total_purchases,
        "receivables": debtors, "payables": creditors, "cash": cash, "bank": bank,
        "net_profit": pnl["net_profit"],
        "recent_invoices": recent_invoices, "recent_bills": recent_bills,
        "sales_counts": sales_counts, "purchase_counts": purchase_counts, "budget_counts": budget_counts,
    })


def _contact_home(request: Request, user: User, db: Session):
    invoices = db.scalars(
        select(CustomerInvoice).where(CustomerInvoice.customer_id == user.contact_id)
        .order_by(CustomerInvoice.id.desc())
    ).all() if user.contact_id else []
    bills = db.scalars(
        select(VendorBill).where(VendorBill.vendor_id == user.contact_id)
        .order_by(VendorBill.id.desc())
    ).all() if user.contact_id else []
    return templates.TemplateResponse(request, "dashboard/contact_home.html", {
        "request": request, "user": user, "active": "my_invoices",
        "invoices": invoices, "bills": bills,
    })
