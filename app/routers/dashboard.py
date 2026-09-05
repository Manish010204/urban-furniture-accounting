from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import (
    Budget,
    BudgetStatus,
    CustomerInvoice,
    InvoiceStatus,
    POStatus,
    PurchaseOrder,
    SalesOrder,
    SOStatus,
    User,
    VendorBill,
)
from app.services import accounting, business_metrics, reports
from app.templating import templates

router = APIRouter()


def _trend_chart(trend: list[dict], width: int = 640, height: int = 200, padding: int = 32) -> dict:
    """Pre-computes SVG polyline coordinates server-side for a simple, dependency-free
    revenue-vs-expense line chart — no charting library needed."""
    n = len(trend)
    values = [p["revenue"] for p in trend] + [p["expenses"] for p in trend]
    max_val = max(values) if values and max(values) > 0 else 1

    def px(i):
        return padding if n <= 1 else padding + i * (width - 2 * padding) / (n - 1)

    def py(v):
        return height - padding - (v / max_val) * (height - 2 * padding)

    revenue_points = " ".join(f"{px(i):.1f},{py(p['revenue']):.1f}" for i, p in enumerate(trend))
    expense_points = " ".join(f"{px(i):.1f},{py(p['expenses']):.1f}" for i, p in enumerate(trend))
    labels = [{"x": px(i), "text": p["label"]} for i, p in enumerate(trend)]
    return {
        "width": width, "height": height, "padding": padding,
        "revenue_points": revenue_points, "expense_points": expense_points, "labels": labels,
        "has_data": any(v > 0 for v in values),
    }


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

    total_sales = pnl["total_income"]
    total_purchases = next((r["balance"] for r in pnl["expenses"]
                             if r["account"].name == accounting.ACCOUNT_PURCHASES_EXPENSE), 0)
    other_expenses = round(pnl["total_expenses"] - total_purchases, 2)

    recent_invoices = db.scalars(select(CustomerInvoice).order_by(CustomerInvoice.id.desc()).limit(5)).all()
    recent_bills = db.scalars(select(VendorBill).order_by(VendorBill.id.desc()).limit(5)).all()

    sales_counts = _status_counts(db, SalesOrder, SalesOrder.status,
                                   (SOStatus.confirmed, SOStatus.invoiced), SOStatus.draft, SOStatus.cancelled)
    purchase_counts = _status_counts(db, PurchaseOrder, PurchaseOrder.status,
                                      (POStatus.confirmed, POStatus.billed), POStatus.draft, POStatus.cancelled)
    budget_counts = _status_counts(db, Budget, Budget.status,
                                    (BudgetStatus.confirmed, BudgetStatus.revised), BudgetStatus.draft,
                                    BudgetStatus.cancelled)

    receivables_detail = business_metrics.receivables_summary(db)
    payables_detail = business_metrics.payables_summary(db)
    trend = business_metrics.revenue_expense_trend(db, months=6)
    greeting_hour = datetime.now().hour
    greeting = "Good morning" if greeting_hour < 12 else "Good afternoon" if greeting_hour < 17 else "Good evening"

    return templates.TemplateResponse(request, "dashboard/index.html", {
        "request": request, "user": user, "active": "dashboard", "greeting": greeting,
        "total_sales": total_sales, "total_purchases": total_purchases, "other_expenses": other_expenses,
        "receivables": receivables_detail["total"], "payables": payables_detail["total"],
        "cash": cash, "bank": bank,
        "net_profit": pnl["net_profit"],
        "recent_invoices": recent_invoices, "recent_bills": recent_bills,
        "sales_counts": sales_counts, "purchase_counts": purchase_counts, "budget_counts": budget_counts,
        "period_comparison": business_metrics.period_comparison(db),
        "pulse": business_metrics.business_pulse(db),
        "trend": trend,
        "chart": _trend_chart(trend),
        "receivables_detail": receivables_detail,
        "payables_detail": payables_detail,
        "action_items": business_metrics.action_center_items(db),
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

    total_invoices = len(invoices)
    paid_invoices = sum(1 for i in invoices if i.status == InvoiceStatus.paid)
    unpaid_invoices = sum(1 for i in invoices if i.status != InvoiceStatus.paid)
    overdue_invoices = [i for i in invoices if i.is_overdue]
    outstanding_amount = round(sum(i.amount_due for i in invoices), 2)

    return templates.TemplateResponse(request, "dashboard/contact_home.html", {
        "request": request, "user": user, "active": "my_invoices",
        "invoices": invoices, "bills": bills,
        "total_invoices": total_invoices, "paid_invoices": paid_invoices,
        "unpaid_invoices": unpaid_invoices, "overdue_invoices": len(overdue_invoices),
        "outstanding_amount": outstanding_amount,
    })
