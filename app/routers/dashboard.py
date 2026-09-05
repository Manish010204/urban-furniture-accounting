from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import CustomerInvoice, User, VendorBill
from app.services import accounting, reports
from app.templating import templates

router = APIRouter()


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

    return templates.TemplateResponse("dashboard/index.html", {
        "request": request, "user": user, "active": "dashboard",
        "total_sales": total_sales, "total_purchases": total_purchases,
        "receivables": debtors, "payables": creditors, "cash": cash, "bank": bank,
        "net_profit": pnl["net_profit"],
        "recent_invoices": recent_invoices, "recent_bills": recent_bills,
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
    return templates.TemplateResponse("dashboard/contact_home.html", {
        "request": request, "user": user, "active": "my_invoices",
        "invoices": invoices, "bills": bills,
    })
