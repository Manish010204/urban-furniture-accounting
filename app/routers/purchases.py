from datetime import date, timedelta
from itertools import zip_longest

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import (
    AnalyticAccount,
    Contact,
    ContactType,
    Journal,
    JournalType,
    Payment,
    PaymentDirection,
    PaymentMethod,
    POStatus,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    User,
    VendorBill,
    VendorBillLine,
)
from app.services import reports as reports_service
from app.services.accounting import ACCOUNT_PURCHASES_EXPENSE, get_account, get_journal, post_vendor_bill, post_vendor_payment
from app.templating import templates
from app.validators import ValidationError

router = APIRouter(prefix="/purchases", tags=["purchases"])


def _vendors(db: Session):
    return db.scalars(
        select(Contact).where(Contact.is_archived == False)  # noqa: E712
        .where(Contact.type.in_([ContactType.vendor, ContactType.both])).order_by(Contact.name)
    ).all()


def _products(db: Session):
    return db.scalars(select(Product).where(Product.is_archived == False).order_by(Product.name)).all()  # noqa: E712


def _analytic_accounts(db: Session):
    return db.scalars(select(AnalyticAccount).where(AnalyticAccount.type == "expense").order_by(AnalyticAccount.name)).all()


@router.get("")
def list_purchase_orders(request: Request, user: User = Depends(require_role("admin", "accountant")),
                          db: Session = Depends(get_db)):
    orders = db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.id.desc())).all()
    bills = db.scalars(select(VendorBill).order_by(VendorBill.id.desc())).all()
    return templates.TemplateResponse(request, "purchases/list.html", {
        "request": request, "user": user, "active": "purchases", "orders": orders, "bills": bills,
    })


@router.get("/new")
def new_po_form(request: Request, vendor_id: int = None, user: User = Depends(require_role("admin", "accountant")),
                db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "purchases/form.html", {
        "request": request, "user": user, "active": "purchases",
        "vendors": _vendors(db), "products": _products(db), "analytic_accounts": _analytic_accounts(db),
        "today": date.today().isoformat(), "selected_vendor_id": vendor_id,
    })


@router.post("/new")
async def create_po(request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    form = await request.form()
    vendor_id = int(form["vendor_id"])
    po_date = date.fromisoformat(form["date"])
    product_ids = form.getlist("product_id")
    qtys = form.getlist("qty")
    prices = form.getlist("unit_price")
    analytic_ids = form.getlist("analytic_account_id")

    def render_error(message):
        return templates.TemplateResponse(request, "purchases/form.html", {
            "request": request, "user": user, "active": "purchases",
            "vendors": _vendors(db), "products": _products(db), "analytic_accounts": _analytic_accounts(db),
            "today": po_date.isoformat(), "error": message,
        }, status_code=400)

    vendor = db.get(Contact, vendor_id)
    if not vendor or vendor.is_archived:
        return render_error("Please select an active vendor.")

    lines = []
    for pid, qty, price, analytic_id in zip_longest(product_ids, qtys, prices, analytic_ids, fillvalue=""):
        if not pid:
            continue
        qty_f, price_f = float(qty or 0), float(price or 0)
        if qty_f <= 0:
            return render_error("Quantity must be greater than zero for every line.")
        if price_f < 0:
            return render_error("Unit price cannot be negative.")
        product = db.get(Product, int(pid))
        if not product or product.is_archived:
            return render_error("One of the selected products is archived or invalid.")
        lines.append(PurchaseOrderLine(
            product_id=product.id, qty=qty_f, unit_price=price_f,
            analytic_account_id=int(analytic_id) if analytic_id else None,
        ))

    if not lines:
        return render_error("Add at least one product line.")

    po = PurchaseOrder(vendor_id=vendor.id, date=po_date, status=POStatus.draft)
    po.lines = lines
    db.add(po)
    db.commit()
    return RedirectResponse(url=f"/purchases/{po.id}?success=Purchase+order+created", status_code=303)


@router.get("/{po_id}")
def po_detail(po_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
              db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    return templates.TemplateResponse(request, "purchases/detail.html", {
        "request": request, "user": user, "active": "purchases", "po": po,
    })


@router.post("/{po_id}/confirm")
def confirm_po(po_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
               db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    if po.status != POStatus.draft:
        return RedirectResponse(url=f"/purchases/{po.id}?error=Only+draft+orders+can+be+confirmed", status_code=303)

    warnings = []
    for line in po.lines:
        if not line.analytic_account_id:
            continue
        result = reports_service.remaining_budget_for_analytic(db, line.analytic_account_id, po.date)
        if result is None:
            continue
        budget, remaining = result
        if line.total > remaining:
            warnings.append(
                f"Line for {line.product.name} (₹{line.total:.2f}) exceeds the remaining budget "
                f"(₹{remaining:.2f}) for '{budget.name}'."
            )

    po.status = POStatus.confirmed
    db.commit()
    if warnings:
        message = "Purchase+order+confirmed.+Warning:+" + "+".join(w.replace(" ", "+") for w in warnings)
        return RedirectResponse(url=f"/purchases/{po.id}?error={message}", status_code=303)
    return RedirectResponse(url=f"/purchases/{po.id}?success=Purchase+order+confirmed", status_code=303)


@router.post("/{po_id}/cancel")
def cancel_po(po_id: int, user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    if po.status not in (POStatus.draft, POStatus.confirmed):
        return RedirectResponse(url=f"/purchases/{po.id}?error=This+order+cannot+be+cancelled", status_code=303)
    po.status = POStatus.cancelled
    db.commit()
    return RedirectResponse(url=f"/purchases/{po.id}?success=Purchase+order+cancelled", status_code=303)


@router.get("/{po_id}/convert")
def convert_po_form(po_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    if po.bill:
        return RedirectResponse(url=f"/purchases/{po.id}?error=This+purchase+order+already+has+a+vendor+bill", status_code=303)
    if po.status != POStatus.confirmed:
        return RedirectResponse(url=f"/purchases/{po.id}?error=Confirm+the+order+before+creating+a+bill", status_code=303)
    today = date.today()
    return templates.TemplateResponse(request, "purchases/convert.html", {
        "request": request, "user": user, "active": "purchases", "po": po,
        "invoice_date": today.isoformat(), "due_date": (today + timedelta(days=15)).isoformat(),
    })


@router.post("/{po_id}/convert")
def convert_po(po_id: int, request: Request, invoice_date: str = Form(...), due_date: str = Form(...),
               reference: str = Form(""), user: User = Depends(require_role("admin", "accountant")),
               db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    if po.bill:
        return RedirectResponse(url=f"/purchases/{po.id}?error=This+purchase+order+already+has+a+vendor+bill", status_code=303)
    if po.status != POStatus.confirmed:
        return RedirectResponse(url=f"/purchases/{po.id}?error=Confirm+the+order+before+creating+a+bill", status_code=303)

    purchases_expense = get_account(db, ACCOUNT_PURCHASES_EXPENSE)
    bill = VendorBill(
        purchase_order_id=po.id, vendor_id=po.vendor_id, reference=reference or None,
        invoice_date=date.fromisoformat(invoice_date), due_date=date.fromisoformat(due_date),
    )
    bill.lines = [
        VendorBillLine(product_id=l.product_id, account_id=purchases_expense.id,
                        analytic_account_id=l.analytic_account_id, qty=l.qty, unit_price=l.unit_price)
        for l in po.lines
    ]
    db.add(bill)
    db.flush()

    purchase_journal = get_journal(db, JournalType.purchase)
    entry = post_vendor_bill(db, bill, purchase_journal)
    bill.journal_entry_id = entry.id
    po.status = POStatus.billed
    db.commit()
    return RedirectResponse(url=f"/purchases/bills/{bill.id}?success=Vendor+bill+created", status_code=303)


@router.get("/bills/{bill_id}")
def bill_detail(bill_id: int, request: Request,
                 user: User = Depends(require_role("admin", "accountant", "contact")), db: Session = Depends(get_db)):
    bill = db.get(VendorBill, bill_id)
    if not bill:
        return RedirectResponse(url="/purchases?error=Vendor+bill+not+found", status_code=303)
    if user.role.value == "contact" and bill.vendor_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+view+your+own+bills", status_code=303)
    return templates.TemplateResponse(request, "purchases/bill_detail.html", {
        "request": request, "user": user, "active": "purchases", "bill": bill,
    })


@router.get("/bills/{bill_id}/pay")
def pay_bill_form(bill_id: int, request: Request,
                   user: User = Depends(require_role("admin", "accountant", "contact")), db: Session = Depends(get_db)):
    bill = db.get(VendorBill, bill_id)
    if not bill:
        return RedirectResponse(url="/purchases?error=Vendor+bill+not+found", status_code=303)
    if user.role.value == "contact" and bill.vendor_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+pay+your+own+bills", status_code=303)
    if bill.status.value == "paid":
        return RedirectResponse(url=f"/purchases/bills/{bill.id}?error=Bill+is+already+fully+paid", status_code=303)
    return templates.TemplateResponse(request, "purchases/pay_bill.html", {
        "request": request, "user": user, "active": "purchases", "bill": bill, "today": date.today().isoformat(),
    })


@router.post("/bills/{bill_id}/pay")
def pay_bill(bill_id: int, request: Request, amount: float = Form(...), method: str = Form(...),
             note: str = Form(""), user: User = Depends(require_role("admin", "accountant", "contact")),
             db: Session = Depends(get_db)):
    bill = db.get(VendorBill, bill_id)
    if not bill:
        return RedirectResponse(url="/purchases?error=Vendor+bill+not+found", status_code=303)
    if user.role.value == "contact" and bill.vendor_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+pay+your+own+bills", status_code=303)

    def render_error(message):
        return templates.TemplateResponse(request, "purchases/pay_bill.html", {
            "request": request, "user": user, "active": "purchases", "bill": bill,
            "today": date.today().isoformat(), "error": message,
        }, status_code=400)

    if bill.status.value == "paid":
        return render_error("This bill is already fully paid.")
    if amount <= 0:
        return render_error("Payment amount must be greater than zero.")
    if amount > bill.amount_due + 0.01:
        return render_error(f"Payment cannot exceed the outstanding amount of ₹{bill.amount_due:.2f}.")

    payment = Payment(
        direction=PaymentDirection.outbound, party_contact_id=bill.vendor_id,
        method=PaymentMethod(method), amount=amount, vendor_bill_id=bill.id, note=note or None,
    )
    db.add(payment)
    db.flush()

    journal_type = JournalType.bank if method == "bank" else JournalType.cash
    journal = get_journal(db, journal_type)
    entry = post_vendor_payment(db, payment, journal)
    payment.journal_entry_id = entry.id
    db.flush()
    bill.status = _bill_status_after_payment(db, bill)
    db.commit()
    return RedirectResponse(url=f"/purchases/bills/{bill.id}?success=Payment+recorded", status_code=303)


def _bill_status_after_payment(db: Session, bill: VendorBill):
    from app.models import BillStatus
    total_paid = db.scalar(select(func.sum(Payment.amount)).where(Payment.vendor_bill_id == bill.id)) or 0
    amount_due = round(bill.total - total_paid, 2)
    if amount_due <= 0.01:
        return BillStatus.paid
    if total_paid > 0:
        return BillStatus.partially_paid
    return BillStatus.unpaid
