from datetime import date, timedelta

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
)
from app.services.accounting import get_journal, post_vendor_bill, post_vendor_payment
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


@router.get("")
def list_purchase_orders(request: Request, user: User = Depends(require_role("admin", "accountant")),
                          db: Session = Depends(get_db)):
    orders = db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.id.desc())).all()
    bills = db.scalars(select(VendorBill).order_by(VendorBill.id.desc())).all()
    return templates.TemplateResponse("purchases/list.html", {
        "request": request, "user": user, "active": "purchases", "orders": orders, "bills": bills,
    })


@router.get("/new")
def new_po_form(request: Request, vendor_id: int = None, user: User = Depends(require_role("admin", "accountant")),
                db: Session = Depends(get_db)):
    analytic_accounts = db.scalars(select(AnalyticAccount).where(AnalyticAccount.type == "expense")).all()
    return templates.TemplateResponse("purchases/form.html", {
        "request": request, "user": user, "active": "purchases",
        "vendors": _vendors(db), "products": _products(db), "analytic_accounts": analytic_accounts,
        "today": date.today().isoformat(), "selected_vendor_id": vendor_id,
    })


@router.post("/new")
async def create_po(request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    form = await request.form()
    vendor_id = int(form["vendor_id"])
    po_date = date.fromisoformat(form["date"])
    analytic_account_id = form.get("analytic_account_id") or None
    product_ids = form.getlist("product_id")
    qtys = form.getlist("qty")
    prices = form.getlist("unit_price")

    def render_error(message):
        analytic_accounts = db.scalars(select(AnalyticAccount).where(AnalyticAccount.type == "expense")).all()
        return templates.TemplateResponse("purchases/form.html", {
            "request": request, "user": user, "active": "purchases",
            "vendors": _vendors(db), "products": _products(db), "analytic_accounts": analytic_accounts,
            "today": po_date.isoformat(), "error": message,
        }, status_code=400)

    vendor = db.get(Contact, vendor_id)
    if not vendor or vendor.is_archived:
        return render_error("Please select an active vendor.")

    lines = []
    for pid, qty, price in zip(product_ids, qtys, prices):
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
        lines.append(PurchaseOrderLine(product_id=product.id, qty=qty_f, unit_price=price_f))

    if not lines:
        return render_error("Add at least one product line.")

    po = PurchaseOrder(vendor_id=vendor.id, date=po_date, status=POStatus.draft,
                        analytic_account_id=int(analytic_account_id) if analytic_account_id else None)
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
    return templates.TemplateResponse("purchases/detail.html", {
        "request": request, "user": user, "active": "purchases", "po": po,
    })


@router.get("/{po_id}/convert")
def convert_po_form(po_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    if po.bill:
        return RedirectResponse(url=f"/purchases/{po.id}?error=This+purchase+order+already+has+a+vendor+bill", status_code=303)
    today = date.today()
    return templates.TemplateResponse("purchases/convert.html", {
        "request": request, "user": user, "active": "purchases", "po": po,
        "invoice_date": today.isoformat(), "due_date": (today + timedelta(days=15)).isoformat(),
    })


@router.post("/{po_id}/convert")
def convert_po(po_id: int, request: Request, invoice_date: str = Form(...), due_date: str = Form(...),
               user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po:
        return RedirectResponse(url="/purchases?error=Purchase+order+not+found", status_code=303)
    if po.bill:
        return RedirectResponse(url=f"/purchases/{po.id}?error=This+purchase+order+already+has+a+vendor+bill", status_code=303)

    bill = VendorBill(
        purchase_order_id=po.id, vendor_id=po.vendor_id,
        invoice_date=date.fromisoformat(invoice_date), due_date=date.fromisoformat(due_date),
        total=po.total,
    )
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
    return templates.TemplateResponse("purchases/bill_detail.html", {
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
    return templates.TemplateResponse("purchases/pay_bill.html", {
        "request": request, "user": user, "active": "purchases", "bill": bill, "today": date.today().isoformat(),
    })


@router.post("/bills/{bill_id}/pay")
def pay_bill(bill_id: int, request: Request, amount: float = Form(...), method: str = Form(...),
             user: User = Depends(require_role("admin", "accountant", "contact")), db: Session = Depends(get_db)):
    bill = db.get(VendorBill, bill_id)
    if not bill:
        return RedirectResponse(url="/purchases?error=Vendor+bill+not+found", status_code=303)
    if user.role.value == "contact" and bill.vendor_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+pay+your+own+bills", status_code=303)

    def render_error(message):
        return templates.TemplateResponse("purchases/pay_bill.html", {
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
        method=PaymentMethod(method), amount=amount, vendor_bill_id=bill.id,
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
