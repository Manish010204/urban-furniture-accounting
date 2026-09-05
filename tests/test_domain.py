from datetime import date, timedelta

import pytest

from app.models import (
    AnalyticAccount,
    AnalyticType,
    Budget,
    BudgetLine,
    BudgetStatus,
    Contact,
    ContactType,
    CustomerInvoice,
    CustomerInvoiceLine,
    JournalType,
    Payment,
    PaymentDirection,
    PaymentMethod,
    Product,
    ProductType,
    PurchaseOrder,
    PurchaseOrderLine,
    SalesOrder,
    SalesOrderLine,
    VendorBill,
    VendorBillLine,
)
from app.services import accounting as acct
from app.services import reports
from app.services.tax import calculate_tax, calculate_totals


# ---------------------------------------------------------------------------
# 1. Tax calculation
# ---------------------------------------------------------------------------

def test_tax_calculation_basic():
    assert calculate_tax(1000, 5) == 50.0
    assert calculate_tax(0, 5) == 0.0
    assert calculate_tax(100, 0) == 0.0


def test_tax_calculation_rejects_negative_inputs():
    with pytest.raises(ValueError):
        calculate_tax(-10, 5)
    with pytest.raises(ValueError):
        calculate_tax(10, -5)


def test_calculate_totals_matches_subtotal_tax_grand_total():
    result = calculate_totals(qty=5, unit_price=4500, tax_percent=5)
    assert result["subtotal"] == 22500.0
    assert result["tax"] == 1125.0
    assert result["total"] == 23625.0


def test_calculate_totals_rejects_zero_or_negative_qty():
    with pytest.raises(ValueError):
        calculate_totals(qty=0, unit_price=10, tax_percent=5)


# ---------------------------------------------------------------------------
# 2 & 3. Purchase / Sales total calculations (model properties)
# ---------------------------------------------------------------------------

def test_purchase_order_total_calculation(db_session):
    vendor = Contact(name="Azure Furniture", type=ContactType.vendor)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db_session.add_all([vendor, chair])
    db_session.flush()

    po = PurchaseOrder(vendor_id=vendor.id, date=date.today())
    po.lines = [PurchaseOrderLine(product_id=chair.id, qty=10, unit_price=2800)]
    db_session.add(po)
    db_session.commit()

    assert po.total == 28000.0


def test_sales_order_total_calculation_with_tax(db_session):
    customer = Contact(name="Nimesh Pathak", type=ContactType.customer)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db_session.add_all([customer, chair])
    db_session.flush()

    so = SalesOrder(customer_id=customer.id, date=date.today())
    so.lines = [SalesOrderLine(product_id=chair.id, qty=5, unit_price=4500, tax_percent=5)]
    db_session.add(so)
    db_session.commit()

    assert so.subtotal == 22500.0
    assert so.tax_amount == 1125.0
    assert so.total == 23625.0


# ---------------------------------------------------------------------------
# 4. Journal entry debit/credit validation
# ---------------------------------------------------------------------------

def test_balanced_journal_entry_is_accepted(seeded_journals):
    db = seeded_journals
    journal = acct.get_journal(db, JournalType.bank)
    bank = acct.get_account(db, acct.ACCOUNT_BANK)
    capital = acct.get_account(db, acct.ACCOUNT_CAPITAL)

    entry = acct.create_journal_entry(
        db, journal, date.today(), "Opening balance",
        [{"account": bank, "debit": 100, "credit": 0}, {"account": capital, "debit": 0, "credit": 100}],
    )
    assert entry.total_debit == entry.total_credit == 100


def test_unbalanced_journal_entry_is_rejected(seeded_journals):
    db = seeded_journals
    journal = acct.get_journal(db, JournalType.bank)
    bank = acct.get_account(db, acct.ACCOUNT_BANK)
    capital = acct.get_account(db, acct.ACCOUNT_CAPITAL)

    with pytest.raises(acct.UnbalancedEntryError):
        acct.create_journal_entry(
            db, journal, date.today(), "Bad entry",
            [{"account": bank, "debit": 100, "credit": 0}, {"account": capital, "debit": 0, "credit": 90}],
        )


# ---------------------------------------------------------------------------
# 5-8. Posting effects for the four core transactions
# ---------------------------------------------------------------------------

def test_vendor_bill_posting_creates_expected_accounting_effect(seeded_journals):
    db = seeded_journals
    vendor = Contact(name="Azure Furniture", type=ContactType.vendor)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db.add_all([vendor, chair])
    db.flush()
    po = PurchaseOrder(vendor_id=vendor.id, date=date.today())
    db.add(po)
    db.flush()
    purchases_expense = acct.get_account(db, acct.ACCOUNT_PURCHASES_EXPENSE)
    bill = VendorBill(purchase_order_id=po.id, vendor_id=vendor.id, invoice_date=date.today(),
                       due_date=date.today() + timedelta(days=15))
    bill.lines = [VendorBillLine(product_id=chair.id, account_id=purchases_expense.id, qty=10, unit_price=2800)]
    db.add(bill)
    db.flush()

    journal = acct.get_journal(db, JournalType.purchase)
    entry = acct.post_vendor_bill(db, bill, journal)
    db.commit()

    assert entry.total_debit == entry.total_credit == 28000
    purchases_expense = acct.get_account(db, acct.ACCOUNT_PURCHASES_EXPENSE)
    creditors = acct.get_account(db, acct.ACCOUNT_CREDITORS)
    assert acct.account_balance(db, purchases_expense) == 28000
    assert acct.account_balance(db, creditors) == 28000


def test_vendor_payment_posting_creates_expected_accounting_effect(seeded_journals):
    db = seeded_journals
    vendor = Contact(name="Azure Furniture", type=ContactType.vendor)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db.add_all([vendor, chair])
    db.flush()
    po = PurchaseOrder(vendor_id=vendor.id, date=date.today())
    db.add(po)
    db.flush()
    purchases_expense = acct.get_account(db, acct.ACCOUNT_PURCHASES_EXPENSE)
    bill = VendorBill(purchase_order_id=po.id, vendor_id=vendor.id, invoice_date=date.today(),
                       due_date=date.today() + timedelta(days=15))
    bill.lines = [VendorBillLine(product_id=chair.id, account_id=purchases_expense.id, qty=10, unit_price=2800)]
    db.add(bill)
    db.flush()
    purchase_journal = acct.get_journal(db, JournalType.purchase)
    acct.post_vendor_bill(db, bill, purchase_journal)
    db.commit()

    payment = Payment(direction=PaymentDirection.outbound, party_contact_id=vendor.id,
                       method=PaymentMethod.bank, amount=28000, vendor_bill_id=bill.id)
    db.add(payment)
    db.flush()
    bank_journal = acct.get_journal(db, JournalType.bank)
    entry = acct.post_vendor_payment(db, payment, bank_journal)
    db.commit()

    assert entry.total_debit == entry.total_credit == 28000
    creditors = acct.get_account(db, acct.ACCOUNT_CREDITORS)
    bank = acct.get_account(db, acct.ACCOUNT_BANK)
    assert acct.account_balance(db, creditors) == 0
    assert acct.account_balance(db, bank) == -28000  # no opening balance in this isolated test


def test_customer_invoice_posting_creates_expected_accounting_effect(seeded_journals):
    db = seeded_journals
    customer = Contact(name="Nimesh Pathak", type=ContactType.customer)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db.add_all([customer, chair])
    db.flush()
    so = SalesOrder(customer_id=customer.id, date=date.today())
    db.add(so)
    db.flush()
    sales_income = acct.get_account(db, acct.ACCOUNT_SALES_INCOME)
    invoice = CustomerInvoice(sales_order_id=so.id, customer_id=customer.id, invoice_date=date.today(),
                               due_date=date.today() + timedelta(days=15))
    invoice.lines = [CustomerInvoiceLine(product_id=chair.id, account_id=sales_income.id,
                                          qty=5, unit_price=4500, tax_percent=5)]
    db.add(invoice)
    db.flush()

    journal = acct.get_journal(db, JournalType.sales)
    entry = acct.post_customer_invoice(db, invoice, journal)
    db.commit()

    assert entry.total_debit == entry.total_credit == 23625
    debtors = acct.get_account(db, acct.ACCOUNT_DEBTORS)
    sales_income = acct.get_account(db, acct.ACCOUNT_SALES_INCOME)
    tax_payable = acct.get_account(db, acct.ACCOUNT_TAX_PAYABLE)
    assert acct.account_balance(db, debtors) == 23625
    assert acct.account_balance(db, sales_income) == 22500
    assert acct.account_balance(db, tax_payable) == 1125


def test_customer_payment_posting_creates_expected_accounting_effect(seeded_journals):
    db = seeded_journals
    customer = Contact(name="Nimesh Pathak", type=ContactType.customer)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db.add_all([customer, chair])
    db.flush()
    so = SalesOrder(customer_id=customer.id, date=date.today())
    db.add(so)
    db.flush()
    sales_income = acct.get_account(db, acct.ACCOUNT_SALES_INCOME)
    invoice = CustomerInvoice(sales_order_id=so.id, customer_id=customer.id, invoice_date=date.today(),
                               due_date=date.today() + timedelta(days=15))
    invoice.lines = [CustomerInvoiceLine(product_id=chair.id, account_id=sales_income.id,
                                          qty=5, unit_price=4500, tax_percent=5)]
    db.add(invoice)
    db.flush()
    sales_journal = acct.get_journal(db, JournalType.sales)
    acct.post_customer_invoice(db, invoice, sales_journal)
    db.commit()

    payment = Payment(direction=PaymentDirection.inbound, party_contact_id=customer.id,
                       method=PaymentMethod.cash, amount=23625, customer_invoice_id=invoice.id)
    db.add(payment)
    db.flush()
    cash_journal = acct.get_journal(db, JournalType.cash)
    entry = acct.post_customer_payment(db, payment, cash_journal)
    db.commit()

    assert entry.total_debit == entry.total_credit == 23625
    debtors = acct.get_account(db, acct.ACCOUNT_DEBTORS)
    cash = acct.get_account(db, acct.ACCOUNT_CASH)
    assert acct.account_balance(db, debtors) == 0
    assert acct.account_balance(db, cash) == 23625


# ---------------------------------------------------------------------------
# 9 & 10. P&L and Balance Sheet
# ---------------------------------------------------------------------------

def test_profit_and_loss_reflects_postings(seeded_journals):
    db = seeded_journals
    vendor = Contact(name="Azure Furniture", type=ContactType.vendor)
    customer = Contact(name="Nimesh Pathak", type=ContactType.customer)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db.add_all([vendor, customer, chair])
    db.flush()

    purchases_expense = acct.get_account(db, acct.ACCOUNT_PURCHASES_EXPENSE)
    sales_income = acct.get_account(db, acct.ACCOUNT_SALES_INCOME)

    po = PurchaseOrder(vendor_id=vendor.id, date=date.today())
    db.add(po)
    db.flush()
    bill = VendorBill(purchase_order_id=po.id, vendor_id=vendor.id, invoice_date=date.today(),
                       due_date=date.today())
    bill.lines = [VendorBillLine(product_id=chair.id, account_id=purchases_expense.id, qty=10, unit_price=2800)]
    db.add(bill)
    db.flush()
    acct.post_vendor_bill(db, bill, acct.get_journal(db, JournalType.purchase))

    so = SalesOrder(customer_id=customer.id, date=date.today())
    db.add(so)
    db.flush()
    invoice = CustomerInvoice(sales_order_id=so.id, customer_id=customer.id, invoice_date=date.today(),
                              due_date=date.today())
    invoice.lines = [CustomerInvoiceLine(product_id=chair.id, account_id=sales_income.id,
                                          qty=5, unit_price=4500, tax_percent=5)]
    db.add(invoice)
    db.flush()
    acct.post_customer_invoice(db, invoice, acct.get_journal(db, JournalType.sales))
    db.commit()

    pnl = reports.profit_and_loss(db)
    assert pnl["total_income"] == 22500
    assert pnl["total_expenses"] == 28000
    assert pnl["net_profit"] == 22500 - 28000


def test_balance_sheet_stays_balanced(seeded_journals):
    db = seeded_journals
    bank = acct.get_account(db, acct.ACCOUNT_BANK)
    capital = acct.get_account(db, acct.ACCOUNT_CAPITAL)
    acct.create_journal_entry(
        db, acct.get_journal(db, JournalType.bank), date.today(), "Opening capital",
        [{"account": bank, "debit": 150000, "credit": 0}, {"account": capital, "debit": 0, "credit": 150000}],
    )
    db.commit()

    bs = reports.balance_sheet(db)
    assert bs["total_assets"] == bs["total_liabilities_and_capital"]


# ---------------------------------------------------------------------------
# 11. Budget variance
# ---------------------------------------------------------------------------

def test_budget_variance_calculation(seeded_journals):
    db = seeded_journals
    customer = Contact(name="Nimesh Pathak", type=ContactType.customer)
    chair = Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800)
    db.add_all([customer, chair])
    db.flush()
    analytic = AnalyticAccount(name="Retail Sales", type=AnalyticType.income)
    db.add(analytic)
    db.flush()
    sales_income = acct.get_account(db, acct.ACCOUNT_SALES_INCOME)

    today = date.today()
    budget = Budget(name="Retail Budget", period_start=today - timedelta(days=5),
                     period_end=today + timedelta(days=5), responsible_person="Nimesh Pathak",
                     status=BudgetStatus.confirmed)
    budget.lines = [BudgetLine(analytic_account_id=analytic.id, committed_amount=30000)]
    db.add(budget)
    db.flush()

    so = SalesOrder(customer_id=customer.id, date=today)
    db.add(so)
    db.flush()
    invoice = CustomerInvoice(sales_order_id=so.id, customer_id=customer.id, invoice_date=today, due_date=today)
    invoice.lines = [CustomerInvoiceLine(product_id=chair.id, account_id=sales_income.id,
                                          analytic_account_id=analytic.id, qty=5, unit_price=4500, tax_percent=0)]
    db.add(invoice)
    db.flush()
    acct.post_customer_invoice(db, invoice, acct.get_journal(db, JournalType.sales))
    db.commit()

    rows = reports.budget_report(db)
    row = next(r for r in rows if r["budget"].id == budget.id)
    line_row = row["lines"][0]
    assert line_row["achieved"] == 22500
    assert line_row["amount_to_achieve"] == 30000 - 22500
