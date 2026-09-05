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
    CustomerInvoice,
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
from app.services.accounting import get_journal, post_customer_invoice, post_customer_payment
from app.templating import templates

router = APIRouter(prefix="/sales", tags=["sales"])


def _customers(db: Session):
    return db.scalars(
        select(Contact).where(Contact.is_archived == False)  # noqa: E712
        .where(Contact.type.in_([ContactType.customer, ContactType.both])).order_by(Contact.name)
    ).all()


def _products(db: Session):
    return db.scalars(select(Product).where(Product.is_archived == False).order_by(Product.name)).all()  # noqa: E712


@router.get("")
def list_sales_orders(request: Request, user: User = Depends(require_role("admin", "accountant")),
                       db: Session = Depends(get_db)):
    orders = db.scalars(select(SalesOrder).order_by(SalesOrder.id.desc())).all()
    invoices = db.scalars(select(CustomerInvoice).order_by(CustomerInvoice.id.desc())).all()
    return templates.TemplateResponse("sales/list.html", {
        "request": request, "user": user, "active": "sales", "orders": orders, "invoices": invoices,
    })


@router.get("/new")
def new_so_form(request: Request, customer_id: int = None, user: User = Depends(require_role("admin", "accountant")),
                db: Session = Depends(get_db)):
    analytic_accounts = db.scalars(select(AnalyticAccount).where(AnalyticAccount.type == "income")).all()
    return templates.TemplateResponse("sales/form.html", {
        "request": request, "user": user, "active": "sales",
        "customers": _customers(db), "products": _products(db), "analytic_accounts": analytic_accounts,
        "today": date.today().isoformat(), "selected_customer_id": customer_id,
    })


@router.post("/new")
async def create_so(request: Request, user: User = Depends(require_role("admin", "accountant")),
                     db: Session = Depends(get_db)):
    form = await request.form()
    customer_id = int(form["customer_id"])
    so_date = date.fromisoformat(form["date"])
    analytic_account_id = form.get("analytic_account_id") or None
    product_ids = form.getlist("product_id")
    qtys = form.getlist("qty")
    prices = form.getlist("unit_price")
    taxes = form.getlist("tax_percent")

    def render_error(message):
        analytic_accounts = db.scalars(select(AnalyticAccount).where(AnalyticAccount.type == "income")).all()
        return templates.TemplateResponse("sales/form.html", {
            "request": request, "user": user, "active": "sales",
            "customers": _customers(db), "products": _products(db), "analytic_accounts": analytic_accounts,
            "today": so_date.isoformat(), "error": message,
        }, status_code=400)

    customer = db.get(Contact, customer_id)
    if not customer or customer.is_archived:
        return render_error("Please select an active customer.")

    lines = []
    for pid, qty, price, tax in zip(product_ids, qtys, prices, taxes):
        if not pid:
            continue
        qty_f, price_f, tax_f = float(qty or 0), float(price or 0), float(tax or 0)
        if qty_f <= 0:
            return render_error("Quantity must be greater than zero for every line.")
        if price_f < 0:
            return render_error("Unit price cannot be negative.")
        if tax_f < 0:
            return render_error("Tax percent cannot be negative.")
        product = db.get(Product, int(pid))
        if not product or product.is_archived:
            return render_error("One of the selected products is archived or invalid.")
        lines.append(SalesOrderLine(product_id=product.id, qty=qty_f, unit_price=price_f, tax_percent=tax_f))

    if not lines:
        return render_error("Add at least one product line.")

    so = SalesOrder(customer_id=customer.id, date=so_date, status=SOStatus.draft,
                     analytic_account_id=int(analytic_account_id) if analytic_account_id else None)
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
    return templates.TemplateResponse("sales/detail.html", {
        "request": request, "user": user, "active": "sales", "so": so,
    })


@router.get("/{so_id}/generate-invoice")
def generate_invoice_form(so_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                           db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    if so.invoice:
        return RedirectResponse(url=f"/sales/{so.id}?error=An+invoice+already+exists+for+this+sales+order", status_code=303)
    today = date.today()
    return templates.TemplateResponse("sales/generate_invoice.html", {
        "request": request, "user": user, "active": "sales", "so": so,
        "invoice_date": today.isoformat(), "due_date": (today + timedelta(days=15)).isoformat(),
    })


@router.post("/{so_id}/generate-invoice")
def generate_invoice(so_id: int, request: Request, invoice_date: str = Form(...), due_date: str = Form(...),
                      user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    so = db.get(SalesOrder, so_id)
    if not so:
        return RedirectResponse(url="/sales?error=Sales+order+not+found", status_code=303)
    if so.invoice:
        return RedirectResponse(url=f"/sales/{so.id}?error=An+invoice+already+exists+for+this+sales+order", status_code=303)

    invoice = CustomerInvoice(
        sales_order_id=so.id, customer_id=so.customer_id,
        invoice_date=date.fromisoformat(invoice_date), due_date=date.fromisoformat(due_date),
        subtotal=so.subtotal, tax_amount=so.tax_amount, total=so.total,
    )
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
    return templates.TemplateResponse("sales/invoice_detail.html", {
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
    return templates.TemplateResponse("sales/pay_invoice.html", {
        "request": request, "user": user, "active": "sales", "invoice": invoice, "today": date.today().isoformat(),
    })


@router.post("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, request: Request, amount: float = Form(...), method: str = Form(...),
                user: User = Depends(require_role("admin", "accountant", "contact")), db: Session = Depends(get_db)):
    invoice = db.get(CustomerInvoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/sales?error=Invoice+not+found", status_code=303)
    if user.role.value == "contact" and invoice.customer_id != user.contact_id:
        return RedirectResponse(url="/?error=You+can+only+pay+your+own+invoices", status_code=303)

    def render_error(message):
        return templates.TemplateResponse("sales/pay_invoice.html", {
            "request": request, "user": user, "active": "sales", "invoice": invoice,
            "today": date.today().isoformat(), "error": message,
        }, status_code=400)

    if invoice.status.value == "paid":
        return render_error("This invoice is already fully paid.")
    if amount <= 0:
        return render_error("Payment amount must be greater than zero.")
    if amount > invoice.amount_due + 0.01:
        return render_error(f"Payment cannot exceed the outstanding amount of ₹{invoice.amount_due:.2f}.")

    payment = Payment(
        direction=PaymentDirection.inbound, party_contact_id=invoice.customer_id,
        method=PaymentMethod(method), amount=amount, customer_invoice_id=invoice.id,
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
    total_paid = db.scalar(select(func.sum(Payment.amount)).where(Payment.customer_invoice_id == invoice.id)) or 0
    amount_due = round(invoice.total - total_paid, 2)
    if amount_due <= 0.01:
        return InvoiceStatus.paid
    if total_paid > 0:
        return InvoiceStatus.partially_paid
    return InvoiceStatus.unpaid
