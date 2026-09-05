"""Reports derived entirely from posted journal entry lines — nothing hardcoded."""
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountType,
    AnalyticAccount,
    Budget,
    BudgetLine,
    BudgetStatus,
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


def _analytic_actual(db: Session, analytic_account: AnalyticAccount, period_start, period_end) -> float:
    query = (
        select(JournalEntryLine)
        .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
        .where(JournalEntryLine.analytic_account_id == analytic_account.id)
        .where(JournalEntry.date >= period_start)
        .where(JournalEntry.date <= period_end)
    )
    rows = db.scalars(query).all()
    if analytic_account.type.value == "income":
        return round(sum(r.credit - r.debit for r in rows), 2)
    return round(sum(r.debit - r.credit for r in rows), 2)


def budget_line_report(db: Session, line: BudgetLine, budget: Budget) -> dict:
    achieved = _analytic_actual(db, line.analytic_account, budget.period_start, budget.period_end)
    achieved_pct = round((achieved / line.committed_amount) * 100, 1) if line.committed_amount else 0.0
    return {
        "line": line,
        "achieved": achieved,
        "achieved_pct": achieved_pct,
        "amount_to_achieve": round(line.committed_amount - achieved, 2),
    }


def budget_report(db: Session) -> list[dict]:
    """One row per budget, each carrying its per-analytic-account lines with
    achieved/achieved%/amount-to-achieve (only meaningful once confirmed)."""
    budgets = db.scalars(select(Budget).order_by(Budget.id.desc())).all()
    results = []
    for budget in budgets:
        show_actuals = budget.status in (BudgetStatus.confirmed, BudgetStatus.revised)
        line_rows = [budget_line_report(db, line, budget) for line in budget.lines] if show_actuals else [
            {"line": line, "achieved": None, "achieved_pct": None, "amount_to_achieve": None} for line in budget.lines
        ]
        total_achieved = round(sum(r["achieved"] for r in line_rows), 2) if show_actuals else None
        results.append({
            "budget": budget,
            "lines": line_rows,
            "total_committed": budget.planned_amount,
            "total_achieved": total_achieved,
            "total_amount_to_achieve": round(budget.planned_amount - total_achieved, 2) if show_actuals else None,
        })
    return results


def remaining_budget_for_analytic(db: Session, analytic_account_id: int, as_of, exclude_transaction_amount: float = 0):
    """Returns (budget, remaining_amount) for the confirmed budget line covering this
    analytic account and date, or None if no confirmed budget covers it."""
    line = db.scalar(
        select(BudgetLine)
        .join(Budget, BudgetLine.budget_id == Budget.id)
        .where(BudgetLine.analytic_account_id == analytic_account_id)
        .where(Budget.status == BudgetStatus.confirmed)
        .where(Budget.period_start <= as_of)
        .where(Budget.period_end >= as_of)
    )
    if line is None:
        return None
    achieved = _analytic_actual(db, line.analytic_account, line.budget.period_start, line.budget.period_end)
    remaining = line.committed_amount - achieved
    return line.budget, remaining
