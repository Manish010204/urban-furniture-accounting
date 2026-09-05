from datetime import date, timedelta
from decimal import Decimal
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
    CustomerInvoice,
    CustomerInvoiceLine,
    InvoiceStatus,
    JournalType,
    Payment,
    PaymentDirection,
    PaymentMethod,
    Product,
    SalesOrder,
    SalesOrderLine,
    SOStatus,
    User,
)
from app.services.accounting import ACCOUNT_SALES_INCOME, get_account, get_journal, post_customer_invoice, post_customer_payment
from app.templating import templates

router = APIRouter(prefix="/sales", tags=["sales"])


def _customers(db: Session):
    return db.scalars(
        select(Contact).where(Contact.is_archived == False)  # noqa: E712
        .where(Contact.type.in_([ContactType.customer, ContactType.both])).order_by(Contact.name)
    ).all()


def _products(db: Session):
    return db.scalars(select(Product).where(Product.is_archived == False).order_by(Product.name)).all()  # noqa: E712


def _analytic_accounts(db: Session):
    return db.scalars(select(AnalyticAccount).where(AnalyticAccount.type == "income").order_by(AnalyticAccount.name)).all()


@router.get("")
def list_sales_orders(request: Request, so_status: str = "", inv_status: str = "",
                       user: User = Depends(require_role("admin", "accountant")),
                       db: Session = Depends(get_db)):
    so_query = select(SalesOrder)
    if so_status:
        so_query = so_query.where(SalesOrder.status == SOStatus(so_status))
    orders = db.scalars(so_query.order_by(SalesOrder.id.desc())).all()

    inv_query = select(CustomerInvoice)
    if inv_status and inv_status != "overdue":
        inv_query = inv_query.where(CustomerInvoice.status == InvoiceStatus(inv_status))
    invoices = db.scalars(inv_query.order_by(CustomerInvoice.id.desc())).all()
    if inv_status == "overdue":
        invoices = [i for i in invoices if i.is_overdue]

    return templates.TemplateResponse(request, "sales/list.html", {
        "request": request, "user": user, "active": "sales", "orders": orders, "invoices": invoices,
        "so_status": so_status, "inv_status": inv_status,
    })


@router.get("/new")
def new_so_form(request: Request, customer_id: int = None, user: User = Depends(require_role("admin", "accountant")),
                db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "sales/form.html", {
        "request": request, "user": user, "active": "sales",
        "customers": _customers(db), "products": _products(db), "analytic_accounts": _analytic_accounts(db),
        "today": date.today().isoformat(), "selected_customer_id": customer_id,
    })


@router.post("/new")
async def create_so(request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    form = await request.form()
    customer_id = int(form["customer_id"])
    so_date = date.fromisoformat(form["date"])
    product_ids = form.getlist("product_id")
    qtys = form.getlist("qty")
    prices = form.getlist("unit_price")
    taxes = form.getlist("tax_percent")
    analytic_ids = form.getlist("analytic_account_id")

    def render_error(message):
        return templates.TemplateResponse(request, "sales/form.html", {
            "request": request, "user": user, "active": "sales",
            "customers": _customers(db), "products": _products(db), "analytic_accounts": _analytic_accounts(db),
            "today": so_date.isoformat(), "error": message,
        }, status_code=400)

    customer = db.get(Contact, customer_id)
    if not customer or customer.is_archived:
        return render_error("Please select an active customer.")

    lines = []
    for pid, qty, price, tax, analytic_id in zip_longest(product_ids, qtys, prices, taxes, analytic_ids, fillvalue=""):
        if not pid:
            continue
        qty_f, price_f, tax_f = Decimal(qty or "0"), Decimal(price or "0"), Decimal(tax or "0")
        if qty_f <= 0:
            return render_error("Quantity must be greater than zero for every line.")
        if price_f < 0:
            return render_error("Unit price cannot be negative.")
        if tax_f < 0:
            return render_error("Tax percent cannot be negative.")
        product = db.get(Product, int(pid))
        if not product or product.is_archived:
            return render_error("One of the selected products is archived or invalid.")
        lines.append(SalesOrderLine(
            product_id=product.id, qty=qty_f, unit_price=price_f, tax_percent=tax_f,
            analytic_account_id=int(analytic_id) if analytic_id else None,
        ))

    if not lines:
        return render_error("Add at least one product line.")

    so = SalesOrder(customer_id=customer.id, date=so_date, status=SOStatus.draft)
    so.lines = lines
    db.add(so)
    db.commit()
    return RedirectResponse(url=f"/sales/{so.id}?success=Sales+order+created", status_code=303)


@router.get("/{so_id}")
def so_detail(so_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
              db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    return templates.TemplateResponse(request, "sales/detail.html", {
        "request": request, "user": user, "active": "sales", "so": so,
    })


@router.post("/{so_id}/confirm")
def confirm_so(so_id: int, user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    if so.status != SOStatus.draft:
        return RedirectResponse(url=f"/sales/{so.id}?error=Only+draft+orders+can+be+confirmed", status_code=303)
    so.status = SOStatus.confirmed
    db.commit()
    return RedirectResponse(url=f"/sales/{so.id}?success=Sales+order+confirmed", status_code=303)


@router.post("/{so_id}/cancel")
def cancel_so(so_id: int, user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    if so.status not in (SOStatus.draft, SOStatus.confirmed):
        return RedirectResponse(url=f"/sales/{so.id}?error=This+order+cannot+be+cancelled", status_code=303)
    so.status = SOStatus.cancelled
    db.commit()
    return RedirectResponse(url=f"/sales/{so.id}?success=Sales+order+cancelled", status_code=303)


@router.get("/{so_id}/generate-invoice")
def generate_invoice_form(so_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                           db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    if so.invoice:
        return RedirectResponse(url=f"/sales/{so.id}?error=An+invoice+already+exists+for+this+sales+order", status_code=303)
    if so.status != SOStatus.confirmed:
        return RedirectResponse(url=f"/sales/{so.id}?error=Confirm+the+order+before+creating+an+invoice", status_code=303)
    today = date.today()
    return templates.TemplateResponse(request, "sales/generate_invoice.html", {
        "request": request, "user": user, "active": "sales", "so": so,
        "invoice_date": today.isoformat(), "due_date": (today + timedelta(days=15)).isoformat(),
    })


@router.post("/{so_id}/generate-invoice")
def generate_invoice(so_id: int, request: Request, invoice_date: str = Form(...), due_date: str = Form(...),
                      reference: str = Form(""), user: User = Depends(require_role("admin", "accountant")),
                      db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    if so.invoice:
        return RedirectResponse(url=f"/sales/{so.id}?error=An+invoice+already+exists+for+this+sales+order", status_code=303)
    if so.status != SOStatus.confirmed:
        return RedirectResponse(url=f"/sales/{so.id}?error=Confirm+the+order+before+creating+an+invoice", status_code=303)

    sales_income = get_account(db, ACCOUNT_SALES_INCOME)
    invoice = CustomerInvoice(
        sales_order_id=so.id, customer_id=so.customer_id, reference=reference or None,
        invoice_date=date.fromisoformat(invoice_date), due_date=date.fromisoformat(due_date),
    )
    invoice.lines = [
        CustomerInvoiceLine(product_id=l.product_id, account_id=sales_income.id,
                             analytic_account_id=l.analytic_account_id, qty=l.qty,
                             unit_price=l.unit_price, tax_percent=l.tax_percent)
        for l in so.lines
    ]
    db.add(invoice)
    db.flush()

    sales_journal = get_journal(db, JournalType.sales)
    entry = post_customer_invoice(db, invoice, sales_journal)
    invoice.journal_entry_id = entry.id
    so.status = SOStatus.invoiced
    db.commit()
    return RedirectResponse(url=f"/sales/invoices/{invoice.id}?success=Customer+invoice+generated", status_code=303)


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: int, request: Request,
                    user: User = Depends(require_role("admin", "accountant", "contact")), db: Session = Depends(get_db)):
    invoice = db.get(CustomerInvoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/sales?error=Invoice+not+found", status_code=303)
    if user.role.value == "contact" and invoice.customer_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+view+your+own+invoices", status_code=303)
    return templates.TemplateResponse(request, "sales/invoice_detail.html", {
        "request": request, "user": user, "active": "sales", "invoice": invoice,
    })


@router.get("/invoices/{invoice_id}/pay")
def pay_invoice_form(invoice_id: int, request: Request,
                      user: User = Depends(require_role("admin", "accountant", "contact")), db: Session = Depends(get_db)):
    invoice = db.get(CustomerInvoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/sales?error=Invoice+not+found", status_code=303)
    if user.role.value == "contact" and invoice.customer_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+pay+your+own+invoices", status_code=303)
    if invoice.status.value == "paid":
        return RedirectResponse(url=f"/sales/invoices/{invoice.id}?error=Invoice+is+already+fully+paid", status_code=303)
    return templates.TemplateResponse(request, "sales/pay_invoice.html", {
        "request": request, "user": user, "active": "sales", "invoice": invoice, "today": date.today().isoformat(),
    })


@router.post("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, request: Request, amount: Decimal = Form(...), method: str = Form(...),
                note: str = Form(""), user: User = Depends(require_role("admin", "accountant", "contact")),
                db: Session = Depends(get_db)):
    invoice = db.get(CustomerInvoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/sales?error=Invoice+not+found", status_code=303)
    if user.role.value == "contact" and invoice.customer_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+pay+your+own+invoices", status_code=303)

    def render_error(message):
        return templates.TemplateResponse(request, "sales/pay_invoice.html", {
            "request": request, "user": user, "active": "sales", "invoice": invoice,
            "today": date.today().isoformat(), "error": message,
        }, status_code=400)

    if invoice.status.value == "paid":
        return render_error("This invoice is already fully paid.")
    if amount <= 0:
        return render_error("Payment amount must be greater than zero.")
    if amount > invoice.amount_due + Decimal("0.01"):
        return render_error(f"Payment cannot exceed the outstanding amount of ₹{invoice.amount_due:.2f}.")

    payment = Payment(
        direction=PaymentDirection.inbound, party_contact_id=invoice.customer_id,
        method=PaymentMethod(method), amount=amount, customer_invoice_id=invoice.id, note=note or None,
    )
    db.add(payment)
    db.flush()

    journal_type = JournalType.bank if method == "bank" else JournalType.cash
    journal = get_journal(db, journal_type)
    entry = post_customer_payment(db, payment, journal)
    payment.journal_entry_id = entry.id
    db.flush()
    invoice.status = _invoice_status_after_payment(db, invoice)
    db.commit()
    return RedirectResponse(url=f"/sales/invoices/{invoice.id}?success=Payment+recorded", status_code=303)


def _invoice_status_after_payment(db: Session, invoice: CustomerInvoice):
    total_paid = db.scalar(select(func.sum(Payment.amount)).where(Payment.customer_invoice_id == invoice.id)) or Decimal("0")
    amount_due = round(invoice.total - total_paid, 2)
    if amount_due <= Decimal("0.01"):
        return InvoiceStatus.paid
    if total_paid > 0:
        return InvoiceStatus.partially_paid
    return InvoiceStatus.unpaid
