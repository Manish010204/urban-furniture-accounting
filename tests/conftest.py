import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Point the app at a fresh, isolated SQLite file before app.database is imported
# by anything else, so tests never touch the real data/app.db used for the demo.
_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

# Matches app/seed.py — the three demo users created on first startup.
SEED_CREDENTIALS = {
    "admin": ("admin1", "Admin@123"),
    "accountant": ("priya1", "Priya@123"),
    "contact": ("nimesh1", "Nimesh@123"),
}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    """An isolated in-memory database for unit-level accounting/domain tests."""
    from app.database import Base
    from app.models import Account, AccountType, Journal, JournalType  # noqa: F401 ensure models registered

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def seeded_accounts(db_session):
    from app.models import Account, AccountType
    from app.services import accounting as acct

    accounts = {
        acct.ACCOUNT_CASH: AccountType.asset,
        acct.ACCOUNT_BANK: AccountType.asset,
        acct.ACCOUNT_DEBTORS: AccountType.asset,
        acct.ACCOUNT_CREDITORS: AccountType.liability,
        acct.ACCOUNT_SALES_INCOME: AccountType.income,
        acct.ACCOUNT_PURCHASES_EXPENSE: AccountType.expense,
        acct.ACCOUNT_TAX_PAYABLE: AccountType.liability,
        acct.ACCOUNT_CAPITAL: AccountType.capital,
    }
    for name, acc_type in accounts.items():
        db_session.add(Account(name=name, type=acc_type))
    db_session.commit()
    return db_session


@pytest.fixture()
def seeded_journals(seeded_accounts):
    from app.models import Journal, JournalType

    journals = {}
    for jtype in (JournalType.sales, JournalType.purchase, JournalType.bank, JournalType.cash):
        j = Journal(name=f"{jtype.value.title()} Journal", type=jtype)
        seeded_accounts.add(j)
        journals[jtype] = j
    seeded_accounts.commit()
    return seeded_accounts
