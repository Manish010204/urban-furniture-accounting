"""Idempotent demo data seeding — runs at startup if the database is empty.

Everything below is built by calling the exact same posting functions the
routers use (post_vendor_bill, post_customer_invoice, post_vendor_payment,
post_customer_payment, create_journal_entry) — nothing here fabricates a
balance or a report number directly. The result is a handful of months of
real, internally-consistent purchase/sales history so the app has something
to look at the moment it's opened, instead of an empty shell.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountType,
    AnalyticAccount,
    AnalyticType,
    BillStatus,
    Budget,
    BudgetLine,
    BudgetStatus,
    Contact,
    ContactType,
    CustomerInvoice,
    CustomerInvoiceLine,
    InvoiceStatus,
    Journal,
    JournalType,
    Payment,
    PaymentDirection,
    PaymentMethod,
    POStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    Product,
    ProductType,
    SalesOrder,
    SalesOrderLine,
    SOStatus,
    User,
    UserRole,
    VendorBill,
    VendorBillLine,
)
from app.security import hash_password
from app.services import accounting


def _po_flow(db, vendor, purchase_journal, purchases_expense, po_date, items,
             confirm=False, invoice_date=None, due_date=None, pay_amount=None, pay_date=None,
             pay_method=PaymentMethod.bank, pay_journal=None):
    """items: list of (product, qty, unit_price, analytic_account_id)."""
    po = PurchaseOrder(vendor_id=vendor.id, date=po_date, status=POStatus.draft)
    po.lines = [
        PurchaseOrderLine(product_id=p.id, qty=Decimal(qty), unit_price=Decimal(price), analytic_account_id=analytic_id)
        for p, qty, price, analytic_id in items
    ]
    db.add(po)
    db.flush()
    if not confirm:
        return po, None

    po.status = POStatus.confirmed
    if due_date is None:
        return po, None

    bill = VendorBill(purchase_order_id=po.id, vendor_id=po.vendor_id,
                       invoice_date=invoice_date or po_date, due_date=due_date)
    bill.lines = [
        VendorBillLine(product_id=l.product_id, account_id=purchases_expense.id,
                        analytic_account_id=l.analytic_account_id, qty=l.qty, unit_price=l.unit_price)
        for l in po.lines
    ]
    db.add(bill)
    db.flush()
    entry = accounting.post_vendor_bill(db, bill, purchase_journal)
    bill.journal_entry_id = entry.id
    po.status = POStatus.billed

    if pay_amount is not None:
        amount = bill.total if pay_amount == "full" else Decimal(str(pay_amount))
        payment = Payment(direction=PaymentDirection.outbound, party_contact_id=bill.vendor_id,
                           method=pay_method, amount=amount, date=pay_date or bill.invoice_date,
                           vendor_bill_id=bill.id)
        db.add(payment)
        db.flush()
        pay_entry = accounting.post_vendor_payment(db, payment, pay_journal)
        payment.journal_entry_id = pay_entry.id
        if bill.amount_due <= Decimal("0.01"):
            bill.status = BillStatus.paid
        elif bill.amount_paid > 0:
            bill.status = BillStatus.partially_paid
    return po, bill


def _so_flow(db, customer, sales_journal, sales_income, so_date, items,
             confirm=False, invoice_date=None, due_date=None, pay_amount=None, pay_date=None,
             pay_method=PaymentMethod.cash, pay_journal=None):
    """items: list of (product, qty, unit_price, tax_percent, analytic_account_id)."""
    so = SalesOrder(customer_id=customer.id, date=so_date, status=SOStatus.draft)
    so.lines = [
        SalesOrderLine(product_id=p.id, qty=Decimal(qty), unit_price=Decimal(price), tax_percent=Decimal(tax),
                        analytic_account_id=analytic_id)
        for p, qty, price, tax, analytic_id in items
    ]
    db.add(so)
    db.flush()
    if not confirm:
        return so, None

    so.status = SOStatus.confirmed
    if due_date is None:
        return so, None

    invoice = CustomerInvoice(sales_order_id=so.id, customer_id=so.customer_id,
                               invoice_date=invoice_date or so_date, due_date=due_date)
    invoice.lines = [
        CustomerInvoiceLine(product_id=l.product_id, account_id=sales_income.id,
                             analytic_account_id=l.analytic_account_id, qty=l.qty,
                             unit_price=l.unit_price, tax_percent=l.tax_percent)
        for l in so.lines
    ]
    db.add(invoice)
    db.flush()
    entry = accounting.post_customer_invoice(db, invoice, sales_journal)
    invoice.journal_entry_id = entry.id
    so.status = SOStatus.invoiced

    if pay_amount is not None:
        amount = invoice.total if pay_amount == "full" else Decimal(str(pay_amount))
        payment = Payment(direction=PaymentDirection.inbound, party_contact_id=invoice.customer_id,
                           method=pay_method, amount=amount, date=pay_date or invoice.invoice_date,
                           customer_invoice_id=invoice.id)
        db.add(payment)
        db.flush()
        pay_entry = accounting.post_customer_payment(db, payment, pay_journal)
        payment.journal_entry_id = pay_entry.id
        if invoice.amount_due <= Decimal("0.01"):
            invoice.status = InvoiceStatus.paid
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.partially_paid
    return so, invoice


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Account)) is not None:
        return  # already seeded

    # --- Chart of Accounts ---------------------------------------------
    accounts = {
        accounting.ACCOUNT_CASH: AccountType.asset,
        accounting.ACCOUNT_BANK: AccountType.asset,
        accounting.ACCOUNT_DEBTORS: AccountType.asset,
        accounting.ACCOUNT_CREDITORS: AccountType.liability,
        accounting.ACCOUNT_SALES_INCOME: AccountType.income,
        accounting.ACCOUNT_PURCHASES_EXPENSE: AccountType.expense,
        accounting.ACCOUNT_TAX_PAYABLE: AccountType.liability,
        accounting.ACCOUNT_CAPITAL: AccountType.capital,
    }
    account_objs = {}
    for i, (name, acc_type) in enumerate(accounts.items(), start=1):
        acc = Account(name=name, type=acc_type, code=f"{i:04d}")
        db.add(acc)
        account_objs[name] = acc
    db.flush()

    # --- Journals ---------------------------------------------------------
    sales_journal = Journal(
        name="Sales Journal", type=JournalType.sales,
        default_debit_account_id=account_objs[accounting.ACCOUNT_DEBTORS].id,
        default_credit_account_id=account_objs[accounting.ACCOUNT_SALES_INCOME].id,
    )
    purchase_journal = Journal(
        name="Purchase Journal", type=JournalType.purchase,
        default_debit_account_id=account_objs[accounting.ACCOUNT_PURCHASES_EXPENSE].id,
        default_credit_account_id=account_objs[accounting.ACCOUNT_CREDITORS].id,
    )
    bank_journal = Journal(
        name="Bank Journal", type=JournalType.bank,
        default_debit_account_id=account_objs[accounting.ACCOUNT_BANK].id,
        default_credit_account_id=account_objs[accounting.ACCOUNT_BANK].id,
    )
    cash_journal = Journal(
        name="Cash Journal", type=JournalType.cash,
        default_debit_account_id=account_objs[accounting.ACCOUNT_CASH].id,
        default_credit_account_id=account_objs[accounting.ACCOUNT_CASH].id,
    )
    db.add_all([sales_journal, purchase_journal, bank_journal, cash_journal])
    db.flush()

    # --- Contacts -----------------------------------------------------
    # NOTE: azure/nimesh/rahul must stay ids 1/2/3 — the test suite posts
    # forms with hardcoded vendor_id="1"/customer_id="2". Any new contact
    # is appended after these three so their ids never shift.
    azure = Contact(name="Azure Furniture", type=ContactType.vendor, email="sales@azurefurniture.example",
                     mobile="9800011122", city="Jodhpur", state="Rajasthan", country="India", pincode="342001")
    nimesh = Contact(name="Nimesh Pathak", type=ContactType.customer, email="nimesh.pathak@example.com",
                      mobile="9811122233", city="Pune", state="Maharashtra", country="India", pincode="411001")
    rahul = Contact(name="Rahul Sharma", type=ContactType.vendor, email="rahul.sharma@woodcraft.example",
                     mobile="9822233344", city="Jaipur", state="Rajasthan", country="India", pincode="302001")
    db.add_all([azure, nimesh, rahul])
    db.flush()

    kavya = Contact(name="Kavya Interiors", type=ContactType.customer, email="kavya@kavyainteriors.example",
                     mobile="9833344455", city="Bengaluru", state="Karnataka", country="India", pincode="560034")
    db.add(kavya)
    db.flush()

    # --- Products -------------------------------------------------------
    # NOTE: order matters — the test suite posts product_id="1" expecting
    # Office Chair. New products must be appended, never inserted before.
    products = [
        Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800, category="Seating"),
        Product(name="Wooden Table", type=ProductType.goods, sales_price=9500, cost_price=6000, category="Tables"),
        Product(name="Sofa", type=ProductType.goods, sales_price=22000, cost_price=15000, category="Seating"),
        Product(name="Dining Table", type=ProductType.goods, sales_price=18000, cost_price=12000, category="Tables"),
        Product(name="Wooden Chair", type=ProductType.goods, sales_price=2800, cost_price=1600, category="Seating"),
    ]
    db.add_all(products)
    db.flush()
    chair, table, sofa, dining, wchair = products

    # --- Analytic Accounts & Budget --------------------------------------
    retail_sales = AnalyticAccount(name="Retail Sales", type=AnalyticType.income)
    store_ops = AnalyticAccount(name="Store Operations", type=AnalyticType.expense)
    db.add_all([retail_sales, store_ops])
    db.flush()

    today = date.today()
    quarter_start = today.replace(day=1)
    quarter_end = quarter_start + timedelta(days=89)
    retail_budget = Budget(
        name="Q Retail Sales Budget", period_start=quarter_start, period_end=quarter_end,
        responsible_person="Nimesh Pathak", status=BudgetStatus.confirmed,
    )
    retail_budget.lines = [BudgetLine(analytic_account_id=retail_sales.id, committed_amount=90000)]
    ops_budget = Budget(
        name="Q Store Operations Budget", period_start=quarter_start, period_end=quarter_end,
        responsible_person="Rahul Sharma", status=BudgetStatus.confirmed,
    )
    ops_budget.lines = [BudgetLine(analytic_account_id=store_ops.id, committed_amount=60000)]
    db.add_all([retail_budget, ops_budget])
    db.flush()

    # --- Opening capital injection (before any of the history below) -----
    opening_date = today - timedelta(days=175)
    accounting.create_journal_entry(
        db, bank_journal, opening_date, "Opening capital investment",
        [
            {"account": account_objs[accounting.ACCOUNT_BANK], "debit": 150000, "credit": 0},
            {"account": account_objs[accounting.ACCOUNT_CAPITAL], "debit": 0, "credit": 150000},
        ],
        source_type="opening_balance",
    )

    purchases_expense = account_objs[accounting.ACCOUNT_PURCHASES_EXPENSE]
    sales_income = account_objs[accounting.ACCOUNT_SALES_INCOME]

    # --- Prior months: fully closed purchase/sales cycles, oldest first --
    # (gives the dashboard's 6-month Revenue vs Expenses trend and the
    # Contact/Product 360 views real, varied history instead of one data point.)
    _po_flow(
        db, azure, purchase_journal, purchases_expense, today - timedelta(days=150),
        [(chair, 10, 2800, None)], confirm=True,
        invoice_date=today - timedelta(days=148), due_date=today - timedelta(days=133),
        pay_amount="full", pay_date=today - timedelta(days=140), pay_journal=bank_journal,
    )
    _so_flow(
        db, nimesh, sales_journal, sales_income, today - timedelta(days=149),
        [(sofa, 2, 22000, 5, None)], confirm=True,
        invoice_date=today - timedelta(days=147), due_date=today - timedelta(days=132),
        pay_amount="full", pay_date=today - timedelta(days=141), pay_journal=cash_journal,
    )

    _po_flow(
        db, rahul, purchase_journal, purchases_expense, today - timedelta(days=120),
        [(table, 5, 6000, None)], confirm=True,
        invoice_date=today - timedelta(days=118), due_date=today - timedelta(days=103),
        pay_amount="full", pay_date=today - timedelta(days=110), pay_journal=bank_journal,
    )
    _so_flow(
        db, kavya, sales_journal, sales_income, today - timedelta(days=119),
        [(dining, 3, 18000, 5, None)], confirm=True,
        invoice_date=today - timedelta(days=117), due_date=today - timedelta(days=102),
        pay_amount="full", pay_date=today - timedelta(days=111), pay_journal=bank_journal,
    )

    _po_flow(
        db, azure, purchase_journal, purchases_expense, today - timedelta(days=90),
        [(dining, 4, 12000, None)], confirm=True,
        invoice_date=today - timedelta(days=88), due_date=today - timedelta(days=73),
        pay_amount="full", pay_date=today - timedelta(days=80), pay_journal=bank_journal,
    )
    _so_flow(
        db, nimesh, sales_journal, sales_income, today - timedelta(days=89),
        [(chair, 10, 4500, 5, None)], confirm=True,
        invoice_date=today - timedelta(days=87), due_date=today - timedelta(days=72),
        pay_amount="full", pay_date=today - timedelta(days=81), pay_journal=cash_journal,
    )
    _so_flow(
        db, kavya, sales_journal, sales_income, today - timedelta(days=88),
        [(wchair, 20, 2800, 0, None)], confirm=True,
        invoice_date=today - timedelta(days=86), due_date=today - timedelta(days=71),
        pay_amount="full", pay_date=today - timedelta(days=79), pay_journal=bank_journal,
    )

    _po_flow(
        db, rahul, purchase_journal, purchases_expense, today - timedelta(days=60),
        [(wchair, 10, 1600, None)], confirm=True,
        invoice_date=today - timedelta(days=58), due_date=today - timedelta(days=43),
        pay_amount="full", pay_date=today - timedelta(days=50), pay_journal=bank_journal,
    )
    _so_flow(
        db, nimesh, sales_journal, sales_income, today - timedelta(days=59),
        [(sofa, 1, 22000, 5, None)], confirm=True,
        invoice_date=today - timedelta(days=57), due_date=today - timedelta(days=42),
        pay_amount="full", pay_date=today - timedelta(days=49), pay_journal=cash_journal,
    )

    _po_flow(
        db, azure, purchase_journal, purchases_expense, today - timedelta(days=30),
        [(chair, 15, 2800, None)], confirm=True,
        invoice_date=today - timedelta(days=28), due_date=today - timedelta(days=13),
        pay_amount="full", pay_date=today - timedelta(days=20), pay_journal=bank_journal,
    )
    _so_flow(
        db, kavya, sales_journal, sales_income, today - timedelta(days=29),
        [(dining, 5, 18000, 5, None)], confirm=True,
        invoice_date=today - timedelta(days=27), due_date=today - timedelta(days=12),
        pay_amount="full", pay_date=today - timedelta(days=19), pay_journal=cash_journal,
    )
    _so_flow(
        db, nimesh, sales_journal, sales_income, today - timedelta(days=28),
        [(table, 4, 9500, 5, None)], confirm=True,
        invoice_date=today - timedelta(days=26), due_date=today - timedelta(days=11),
        pay_amount="full", pay_date=today - timedelta(days=18), pay_journal=bank_journal,
    )

    # --- This month: a live, mixed bag so the dashboard's Action Center, ---
    # status filters, and Budget Report all have something real to show.
    # Bill/invoice dates sit inside the current budget period (>= quarter_start);
    # due dates are set relative to `today` so overdue/due-soon actually trigger.
    _po_flow(  # overdue vendor bill -> Action Center + Store Operations budget
        db, azure, purchase_journal, purchases_expense, today - timedelta(days=25),
        [(sofa, 3, 15000, store_ops.id)], confirm=True,
        invoice_date=quarter_start + timedelta(days=1), due_date=quarter_start + timedelta(days=3),
    )
    _po_flow(  # bill due soon -> Action Center
        db, rahul, purchase_journal, purchases_expense, today - timedelta(days=15),
        [(chair, 5, 2800, None)], confirm=True,
        invoice_date=quarter_start + timedelta(days=2), due_date=today + timedelta(days=5),
    )
    _po_flow(  # still sitting in Draft -> Action Center draft-order nudge
        db, azure, purchase_journal, purchases_expense, today - timedelta(days=1),
        [(wchair, 8, 1600, store_ops.id)], confirm=False,
    )

    _so_flow(  # overdue customer invoice -> Action Center + Retail Sales budget
        db, nimesh, sales_journal, sales_income, today - timedelta(days=20),
        [(sofa, 2, 22000, 5, retail_sales.id)], confirm=True,
        invoice_date=quarter_start + timedelta(days=1), due_date=quarter_start + timedelta(days=4),
    )
    _so_flow(  # partially paid -> Retail Sales budget + Partially Paid filter chip
        db, kavya, sales_journal, sales_income, today - timedelta(days=10),
        [(dining, 4, 18000, 5, retail_sales.id)], confirm=True,
        invoice_date=quarter_start + timedelta(days=3), due_date=today + timedelta(days=10),
        pay_amount=40000, pay_date=today - timedelta(days=1), pay_journal=cash_journal,
    )
    _so_flow(  # still sitting in Draft -> Action Center draft-order nudge
        db, nimesh, sales_journal, sales_income, today,
        [(wchair, 15, 2800, 0, retail_sales.id)], confirm=False,
    )
    _so_flow(  # fully closed today, same-day payment -> proves the live flow end-to-end
        db, kavya, sales_journal, sales_income, today,
        [(chair, 2, 4500, 5, retail_sales.id)], confirm=True,
        invoice_date=today, due_date=today + timedelta(days=15),
        pay_amount="full", pay_date=today, pay_journal=cash_journal,
    )

    # --- Users (demo login credentials — see README for the full list) ----
    db.add(User(name="Admin User", login_id="admin1", email="admin@urbanfurniture.test",
                password_hash=hash_password("Admin@123"), role=UserRole.admin))
    db.add(User(name="Priya Verma", login_id="priya1", email="priya@urbanfurniture.test",
                password_hash=hash_password("Priya@123"), role=UserRole.accountant))
    db.add(User(name="Nimesh Pathak", login_id="nimesh1", email="nimesh.user@urbanfurniture.test",
                password_hash=hash_password("Nimesh@123"), role=UserRole.contact, contact_id=nimesh.id))
    db.flush()


    db.commit()
