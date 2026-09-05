"""Minimal double-entry accounting engine.

Every posted journal entry must have total debit == total credit. Account
balances are never stored — they are always derived by summing journal entry
lines, so reports can never drift out of sync with postings.
"""
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountType, Journal, JournalEntry, JournalEntryLine

ACCOUNT_CASH = "Cash"
ACCOUNT_BANK = "Bank"
ACCOUNT_DEBTORS = "Debtors"
ACCOUNT_CREDITORS = "Creditors"
ACCOUNT_SALES_INCOME = "Sales Income"
ACCOUNT_PURCHASES_EXPENSE = "Purchases Expense"
ACCOUNT_TAX_PAYABLE = "Tax Payable"
ACCOUNT_CAPITAL = "Capital"


class UnbalancedEntryError(ValueError):
    pass


def get_account(db: Session, name: str) -> Account:
    account = db.scalar(select(Account).where(Account.name == name))
    if account is None:
        raise LookupError(f"Required account '{name}' not found. Has the database been seeded?")
    return account


def get_journal(db: Session, journal_type) -> Journal:
    journal = db.scalar(select(Journal).where(Journal.type == journal_type))
    if journal is None:
        raise LookupError(f"Required journal of type '{journal_type}' not found.")
    return journal


def create_journal_entry(
    db: Session,
    journal: Journal,
    entry_date: date_type,
    reference: str,
    lines: list[dict],
    source_type: str | None = None,
    source_id: int | None = None,
) -> JournalEntry:
    """lines: list of {"account": Account, "debit": float, "credit": float, "analytic_account_id": int|None}"""
    total_debit = round(sum(l.get("debit", 0) for l in lines), 2)
    total_credit = round(sum(l.get("credit", 0) for l in lines), 2)
    if total_debit != total_credit:
        raise UnbalancedEntryError(
            f"Journal entry is not balanced: total debit {total_debit} != total credit {total_credit}"
        )
    if total_debit <= 0:
        raise UnbalancedEntryError("Journal entry must have a positive total.")

    entry = JournalEntry(
        journal_id=journal.id,
        date=entry_date,
        reference=reference,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(entry)
    db.flush()

    for line in lines:
        db.add(
            JournalEntryLine(
                entry_id=entry.id,
                account_id=line["account"].id,
                debit=round(line.get("debit", 0), 2),
                credit=round(line.get("credit", 0), 2),
                analytic_account_id=line.get("analytic_account_id"),
            )
        )
    db.flush()
    return entry


def account_raw_balance(db: Session, account: Account) -> float:
    """debit - credit, summed across all posted lines for this account."""
    rows = db.scalars(select(JournalEntryLine).where(JournalEntryLine.account_id == account.id)).all()
    return round(sum(r.debit - r.credit for r in rows), 2)


def account_balance(db: Session, account: Account) -> float:
    """Balance presented in its natural sign: positive for assets/expenses when
    debit-heavy, positive for liabilities/income/capital when credit-heavy."""
    raw = account_raw_balance(db, account)
    if account.type in (AccountType.asset, AccountType.expense):
        return raw
    return -raw


def post_vendor_bill(db: Session, bill, journal: Journal) -> JournalEntry:
    purchases_expense = get_account(db, ACCOUNT_PURCHASES_EXPENSE)
    creditors = get_account(db, ACCOUNT_CREDITORS)
    analytic_account_id = bill.purchase_order.analytic_account_id if bill.purchase_order else None
    entry = create_journal_entry(
        db,
        journal,
        bill.invoice_date,
        f"Vendor Bill #{bill.id}",
        [
            {"account": purchases_expense, "debit": bill.total, "credit": 0, "analytic_account_id": analytic_account_id},
            {"account": creditors, "debit": 0, "credit": bill.total},
        ],
        source_type="vendor_bill",
        source_id=bill.id,
    )
    return entry


def post_customer_invoice(db: Session, invoice, journal: Journal) -> JournalEntry:
    debtors = get_account(db, ACCOUNT_DEBTORS)
    sales_income = get_account(db, ACCOUNT_SALES_INCOME)
    analytic_account_id = invoice.sales_order.analytic_account_id if invoice.sales_order else None
    lines = [{"account": debtors, "debit": invoice.total, "credit": 0}]
    lines.append({"account": sales_income, "debit": 0, "credit": invoice.subtotal, "analytic_account_id": analytic_account_id})
    if invoice.tax_amount > 0:
        tax_payable = get_account(db, ACCOUNT_TAX_PAYABLE)
        lines.append({"account": tax_payable, "debit": 0, "credit": invoice.tax_amount})
    entry = create_journal_entry(
        db,
        journal,
        invoice.invoice_date,
        f"Customer Invoice #{invoice.id}",
        lines,
        source_type="customer_invoice",
        source_id=invoice.id,
    )
    return entry


def post_vendor_payment(db: Session, payment, journal: Journal) -> JournalEntry:
    creditors = get_account(db, ACCOUNT_CREDITORS)
    cash_or_bank = get_account(db, ACCOUNT_BANK if payment.method.value == "bank" else ACCOUNT_CASH)
    entry = create_journal_entry(
        db,
        journal,
        payment.date,
        f"Vendor Payment #{payment.id}",
        [
            {"account": creditors, "debit": payment.amount, "credit": 0},
            {"account": cash_or_bank, "debit": 0, "credit": payment.amount},
        ],
        source_type="payment",
        source_id=payment.id,
    )
    return entry


def post_customer_payment(db: Session, payment, journal: Journal) -> JournalEntry:
    debtors = get_account(db, ACCOUNT_DEBTORS)
    cash_or_bank = get_account(db, ACCOUNT_BANK if payment.method.value == "bank" else ACCOUNT_CASH)
    entry = create_journal_entry(
        db,
        journal,
        payment.date,
        f"Customer Payment #{payment.id}",
        [
            {"account": cash_or_bank, "debit": payment.amount, "credit": 0},
            {"account": debtors, "debit": 0, "credit": payment.amount},
        ],
        source_type="payment",
        source_id=payment.id,
    )
    return entry
