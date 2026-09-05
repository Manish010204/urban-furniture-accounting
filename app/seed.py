"""Idempotent demo data seeding — runs at startup if the database is empty."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountType,
    AnalyticAccount,
    AnalyticType,
    Budget,
    Contact,
    ContactType,
    Journal,
    JournalType,
    Product,
    ProductType,
    User,
    UserRole,
)
from app.services import accounting


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
    azure = Contact(name="Azure Furniture", type=ContactType.vendor, email="sales@azurefurniture.example",
                     mobile="9800011122", city="Jodhpur", state="Rajasthan", pincode="342001")
    nimesh = Contact(name="Nimesh Pathak", type=ContactType.customer, email="nimesh.pathak@example.com",
                      mobile="9811122233", city="Pune", state="Maharashtra", pincode="411001")
    rahul = Contact(name="Rahul Sharma", type=ContactType.vendor, email="rahul.sharma@woodcraft.example",
                     mobile="9822233344", city="Jaipur", state="Rajasthan", pincode="302001")
    db.add_all([azure, nimesh, rahul])
    db.flush()

    # --- Products -------------------------------------------------------
    products = [
        Product(name="Office Chair", type=ProductType.goods, sales_price=4500, cost_price=2800, category="Seating"),
        Product(name="Wooden Table", type=ProductType.goods, sales_price=9500, cost_price=6000, category="Tables"),
        Product(name="Sofa", type=ProductType.goods, sales_price=22000, cost_price=15000, category="Seating"),
        Product(name="Dining Table", type=ProductType.goods, sales_price=18000, cost_price=12000, category="Tables"),
        Product(name="Wooden Chair", type=ProductType.goods, sales_price=2800, cost_price=1600, category="Seating"),
    ]
    db.add_all(products)
    db.flush()

    # --- Analytic Accounts & Budget --------------------------------------
    retail_sales = AnalyticAccount(name="Retail Sales", type=AnalyticType.income)
    store_ops = AnalyticAccount(name="Store Operations", type=AnalyticType.expense)
    db.add_all([retail_sales, store_ops])
    db.flush()

    today = date.today()
    quarter_start = today.replace(day=1)
    quarter_end = quarter_start + timedelta(days=89)
    db.add(Budget(
        name="Q Retail Sales Budget", period_start=quarter_start, period_end=quarter_end,
        responsible_person="Priya Verma", planned_amount=50000, analytic_account_id=retail_sales.id,
    ))
    db.add(Budget(
        name="Q Store Operations Budget", period_start=quarter_start, period_end=quarter_end,
        responsible_person="Ankit Rao", planned_amount=20000, analytic_account_id=store_ops.id,
    ))

    # --- Users (demo login / role switcher) ------------------------------
    db.add(User(name="Admin User", role=UserRole.admin))
    db.add(User(name="Priya Verma (Accountant)", role=UserRole.accountant))
    db.add(User(name="Nimesh Pathak (Contact)", role=UserRole.contact, contact_id=nimesh.id))
    db.flush()

    # --- Opening capital injection so Bank has funds to pay bills ---------
    opening_date = today - timedelta(days=45)
    accounting.create_journal_entry(
        db,
        bank_journal,
        opening_date,
        "Opening capital investment",
        [
            {"account": account_objs[accounting.ACCOUNT_BANK], "debit": 150000, "credit": 0},
            {"account": account_objs[accounting.ACCOUNT_CAPITAL], "debit": 0, "credit": 150000},
        ],
        source_type="opening_balance",
    )

    db.commit()
