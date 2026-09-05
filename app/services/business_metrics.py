"""Dashboard/business-command-center aggregates. Every number here is derived
from real ledger/transaction data via services.reports and services.accounting
— nothing is hardcoded or fabricated."""
from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BillStatus,
    BudgetStatus,
    CustomerInvoice,
    InvoiceStatus,
    POStatus,
    PurchaseOrder,
    SalesOrder,
    SOStatus,
    VendorBill,
)
from app.services import accounting, reports

DUE_SOON_DAYS = 7
BUDGET_WARNING_THRESHOLD_PCT = 90.0


def _month_bounds(months_ago: int, today: date) -> tuple[date, date]:
    year = today.year
    month = today.month - months_ago
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def revenue_expense_trend(db: Session, months: int = 6, today: date | None = None) -> list[dict]:
    """Real monthly Sales Income vs Purchases Expense, oldest to newest."""
    today = today or date.today()
    points = []
    for i in range(months - 1, -1, -1):
        start, end = _month_bounds(i, today)
        pnl = reports.profit_and_loss(db, since=start, as_of=end)
        points.append({
            "label": start.strftime("%b %Y"),
            "revenue": pnl["total_income"],
            "expenses": pnl["total_expenses"],
        })
    return points


def period_comparison(db: Session, today: date | None = None) -> dict:
    """This calendar month vs the previous one, for KPI trend arrows. Returns
    None for a metric's change when the previous period has no data to compare
    against (never fabricates a percentage)."""
    today = today or date.today()
    this_start, this_end = _month_bounds(0, today)
    prev_start, prev_end = _month_bounds(1, today)

    this_pnl = reports.profit_and_loss(db, since=this_start, as_of=this_end)
    prev_pnl = reports.profit_and_loss(db, since=prev_start, as_of=prev_end)

    def pct_change(current, previous):
        if not previous:
            return None
        return round((current - previous) / abs(previous) * 100, 1)

    return {
        "revenue": {"current": this_pnl["total_income"], "change_pct": pct_change(this_pnl["total_income"], prev_pnl["total_income"])},
        "expenses": {"current": this_pnl["total_expenses"], "change_pct": pct_change(this_pnl["total_expenses"], prev_pnl["total_expenses"])},
        "net_profit": {"current": this_pnl["net_profit"], "change_pct": pct_change(this_pnl["net_profit"], prev_pnl["net_profit"])},
    }


def receivables_summary(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    debtors = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_DEBTORS))
    open_invoices = db.scalars(
        select(CustomerInvoice).where(CustomerInvoice.status != InvoiceStatus.paid)
    ).all()
    overdue = [inv for inv in open_invoices if inv.due_date < today]
    return {
        "total": debtors,
        "open_count": len(open_invoices),
        "overdue_amount": round(sum(inv.amount_due for inv in overdue), 2),
        "overdue_count": len(overdue),
    }


def payables_summary(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    creditors = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_CREDITORS))
    open_bills = db.scalars(
        select(VendorBill).where(VendorBill.status != BillStatus.paid)
    ).all()
    overdue = [b for b in open_bills if b.due_date < today]
    due_soon = [b for b in open_bills if today <= b.due_date <= today + timedelta(days=DUE_SOON_DAYS)]
    return {
        "total": creditors,
        "open_count": len(open_bills),
        "due_soon_amount": round(sum(b.amount_due for b in due_soon), 2),
        "due_soon_count": len(due_soon),
        "overdue_amount": round(sum(b.amount_due for b in overdue), 2),
        "overdue_count": len(overdue),
    }


def business_pulse(db: Session) -> dict:
    """Four qualitative indicators, each derived from a clearly-defined
    real ratio — not an arbitrary score."""
    pnl = reports.profit_and_loss(db)
    margin = round(pnl["net_profit"] / pnl["total_income"] * 100, 1) if pnl["total_income"] else None
    if margin is None:
        profitability = {"label": "No sales yet", "tone": "neutral", "detail": "No income recorded."}
    elif margin >= 15:
        profitability = {"label": "Healthy", "tone": "good", "detail": f"{margin}% net margin"}
    elif margin >= 0:
        profitability = {"label": "Tight", "tone": "warning", "detail": f"{margin}% net margin"}
    else:
        profitability = {"label": "Loss-making", "tone": "bad", "detail": f"{margin}% net margin"}

    cash = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_CASH))
    bank = accounting.account_balance(db, accounting.get_account(db, accounting.ACCOUNT_BANK))
    payables = payables_summary(db)
    liquid = cash + bank
    if payables["total"] <= 0:
        cash_position = {"label": "Strong", "tone": "good", "detail": "No outstanding payables"}
    else:
        cover_ratio = round(liquid / payables["total"], 2)
        if cover_ratio >= 1:
            cash_position = {"label": "Strong", "tone": "good", "detail": f"{cover_ratio}x payables covered"}
        elif cover_ratio >= 0.5:
            cash_position = {"label": "Adequate", "tone": "warning", "detail": f"{cover_ratio}x payables covered"}
        else:
            cash_position = {"label": "Stretched", "tone": "bad", "detail": f"{cover_ratio}x payables covered"}

    all_invoices = db.scalars(select(CustomerInvoice)).all()
    invoiced_total = round(sum(inv.total for inv in all_invoices), 2)
    collected_total = round(sum(inv.amount_paid for inv in all_invoices), 2)
    if invoiced_total <= 0:
        collections = {"label": "No invoices yet", "tone": "neutral", "detail": "—"}
    else:
        collection_rate = round(collected_total / invoiced_total * 100, 1)
        tone = "good" if collection_rate >= 80 else "warning" if collection_rate >= 50 else "bad"
        collections = {"label": f"{collection_rate}% collected", "tone": tone,
                        "detail": f"₹{collected_total:.0f} of ₹{invoiced_total:.0f} invoiced"}

    confirmed_budget_rows = [r for r in reports.budget_report(db) if r["budget"].status in
                              (BudgetStatus.confirmed, BudgetStatus.revised)]
    line_pcts = [lr["achieved_pct"] for r in confirmed_budget_rows for lr in r["lines"] if lr["achieved_pct"] is not None]
    if not line_pcts:
        budget_control = {"label": "No active budgets", "tone": "neutral", "detail": "—"}
    else:
        avg_pct = round(sum(line_pcts) / len(line_pcts), 1)
        over_threshold = sum(1 for p in line_pcts if p >= BUDGET_WARNING_THRESHOLD_PCT)
        tone = "bad" if over_threshold else ("warning" if avg_pct >= 70 else "good")
        detail = f"{over_threshold} line(s) near/over limit" if over_threshold else f"{avg_pct}% avg utilization"
        budget_control = {"label": f"{avg_pct}% avg utilization", "tone": tone, "detail": detail}

    return {
        "profitability": profitability,
        "cash_position": cash_position,
        "collections": collections,
        "budget_control": budget_control,
    }


def action_center_items(db: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    items = []

    recv = receivables_summary(db, today)
    if recv["overdue_count"]:
        items.append({
            "level": "red", "text": f"{recv['overdue_count']} customer invoice(s) are overdue",
            "amount": recv["overdue_amount"], "action": "Review", "url": "/sales#invoices",
        })

    pay = payables_summary(db, today)
    if pay["due_soon_count"]:
        items.append({
            "level": "amber", "text": f"{pay['due_soon_count']} vendor bill(s) are due soon",
            "amount": pay["due_soon_amount"], "action": "Review", "url": "/purchases#bills",
        })
    if pay["overdue_count"]:
        items.append({
            "level": "red", "text": f"{pay['overdue_count']} vendor bill(s) are overdue",
            "amount": pay["overdue_amount"], "action": "Review", "url": "/purchases#bills",
        })

    for row in reports.budget_report(db):
        if row["budget"].status not in (BudgetStatus.confirmed, BudgetStatus.revised):
            continue
        for lr in row["lines"]:
            if lr["achieved_pct"] is not None and lr["achieved_pct"] >= BUDGET_WARNING_THRESHOLD_PCT:
                items.append({
                    "level": "yellow",
                    "text": f"Budget '{row['budget'].name}' has crossed {BUDGET_WARNING_THRESHOLD_PCT:.0f}% utilization",
                    "amount": None, "action": "View Budget", "url": f"/budgets/{row['budget'].id}",
                })

    draft_so = db.scalar(select(func.count()).select_from(SalesOrder).where(SalesOrder.status == SOStatus.draft)) or 0
    if draft_so:
        items.append({
            "level": "blue", "text": f"{draft_so} sales order(s) are still in draft",
            "amount": None, "action": "Complete", "url": "/sales",
        })
    draft_po = db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status == POStatus.draft)) or 0
    if draft_po:
        items.append({
            "level": "blue", "text": f"{draft_po} purchase order(s) are still in draft",
            "amount": None, "action": "Complete", "url": "/purchases",
        })

    return items
