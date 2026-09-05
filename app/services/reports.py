"""Reports derived entirely from posted journal entry lines — nothing hardcoded."""
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountType,
    AnalyticAccount,
    Budget,
    JournalEntry,
    JournalEntryLine,
)


def _account_balance_as_of(db: Session, account: Account, as_of: date_type | None) -> float:
    query = (
        select(JournalEntryLine)
        .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
        .where(JournalEntryLine.account_id == account.id)
    )
    if as_of is not None:
        query = query.where(JournalEntry.date <= as_of)
    rows = db.scalars(query).all()
    raw = round(sum(r.debit - r.credit for r in rows), 2)
    if account.type in (AccountType.asset, AccountType.expense):
        return raw
    return -raw


def balance_sheet(db: Session, as_of: date_type | None = None) -> dict:
    accounts = db.scalars(select(Account).where(Account.is_archived == False)).all()  # noqa: E712
    assets = []
    liabilities = []
    capital = []
    for acc in accounts:
        balance = _account_balance_as_of(db, acc, as_of)
        row = {"account": acc, "balance": balance}
        if acc.type == AccountType.asset:
            assets.append(row)
        elif acc.type == AccountType.liability:
            liabilities.append(row)
        elif acc.type == AccountType.capital:
            capital.append(row)

    total_assets = round(sum(r["balance"] for r in assets), 2)
    total_liabilities = round(sum(r["balance"] for r in liabilities), 2)

    # Retained earnings (net profit not yet transferred to capital) keep the
    # balance sheet balanced for demo purposes: Assets = Liabilities + Capital.
    total_capital_recorded = round(sum(r["balance"] for r in capital), 2)
    pnl = profit_and_loss(db, as_of=as_of)
    retained_earnings = pnl["net_profit"]

    return {
        "as_of": as_of,
        "assets": assets,
        "liabilities": liabilities,
        "capital": capital,
        "retained_earnings": retained_earnings,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_capital": round(total_capital_recorded + retained_earnings, 2),
        "total_liabilities_and_capital": round(total_liabilities + total_capital_recorded + retained_earnings, 2),
    }


def profit_and_loss(db: Session, as_of: date_type | None = None, since: date_type | None = None) -> dict:
    accounts = db.scalars(select(Account).where(Account.is_archived == False)).all()  # noqa: E712
    income_rows = []
    expense_rows = []
    for acc in accounts:
        if acc.type not in (AccountType.income, AccountType.expense):
            continue
        query = (
            select(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
            .where(JournalEntryLine.account_id == acc.id)
        )
        if since is not None:
            query = query.where(JournalEntry.date >= since)
        if as_of is not None:
            query = query.where(JournalEntry.date <= as_of)
        rows = db.scalars(query).all()
        raw = round(sum(r.debit - r.credit for r in rows), 2)
        if acc.type == AccountType.income:
            income_rows.append({"account": acc, "balance": round(-raw, 2)})
        else:
            expense_rows.append({"account": acc, "balance": round(raw, 2)})

    total_income = round(sum(r["balance"] for r in income_rows), 2)
    total_expense = round(sum(r["balance"] for r in expense_rows), 2)
    return {
        "as_of": as_of,
        "since": since,
        "income": income_rows,
        "expenses": expense_rows,
        "total_income": total_income,
        "total_expenses": total_expense,
        "net_profit": round(total_income - total_expense, 2),
    }


def budget_report(db: Session) -> list[dict]:
    budgets = db.scalars(select(Budget)).all()
    results = []
    for budget in budgets:
        query = (
            select(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
            .where(JournalEntryLine.analytic_account_id == budget.analytic_account_id)
            .where(JournalEntry.date >= budget.period_start)
            .where(JournalEntry.date <= budget.period_end)
        )
        rows = db.scalars(query).all()
        if budget.analytic_account.type.value == "income":
            actual = round(sum(r.credit - r.debit for r in rows), 2)
        else:
            actual = round(sum(r.debit - r.credit for r in rows), 2)
        results.append(
            {
                "budget": budget,
                "actual": actual,
                "variance": round(budget.planned_amount - actual, 2),
            }
        )
    return results
