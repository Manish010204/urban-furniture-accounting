# Urban Furniture Accounting System

A hackathon prototype accounting system for Urban Furniture — master data,
purchase/sales transaction flows, double-entry bookkeeping, and financial
reports, built as one simple FastAPI + SQLite application.

> This is a **prototype**, not a production accounting system. See
> [Known Limitations](#known-limitations) below.

## 1. Overview

The system implements the full accounting workflow described in the
project specification:

```
Master Data → Purchase/Sales Transaction → Bill/Invoice → Payment
  → Accounting Journal Entry → Ledger/Account Balances → Financial Reports
```

Two people can walk through the whole thing in under 10 minutes: buy
furniture on credit from a vendor and pay the bill, then sell furniture to
a customer (with tax) and receive payment — watching the Chart of Accounts,
Balance Sheet, and P&L update live from the postings.

## 2. Features

**Business Command Center dashboard** — a role-aware executive dashboard:
KPI cards (Revenue/Expenses/Net Profit this month, with month-over-month
trend, plus all-time totals; Cash+Bank; Receivables; Payables), a Business
Pulse panel (Profitability/Cash Position/Collections/Budget Control, each
a clearly-defined real ratio, not an arbitrary score), a Revenue-vs-Expense
trend chart (last 6 months, plain inline SVG — no charting dependency), a
dynamic Action Center (overdue invoices/bills, bills due soon, budgets near
their limit, orders stuck in draft — generated from real data, shows
"You're all caught up" when there's nothing to flag), and Quick Actions.
Accountants see the same page with an operational focus (Pulse/chart
hidden); Contact-role users get a separate "My Financial Portal" instead
(their own invoice/bill counts and outstanding balance only).

**Master Data** — Contacts (customer/vendor/both, with a 360° view showing
total sales/purchases, paid, outstanding and overdue per contact), Products
(goods/service/combo, with gross margin and sales/purchase activity),
Chart of Accounts, Journals, Journal Entries (manual, double-entry
validated, with an optional Partner per line), Analytic Accounts, Budgets
(multi-line, Draft/Confirm/Revise/Cancel lifecycle, with visual progress
bars per analytic-account line).

**Transactions** — Purchase Orders → Confirm → Vendor Bills → Vendor
Payments; Sales Orders (with tax) → Confirm → Customer Invoices → Customer
Payments — both with status filter chips (Draft/Confirmed/.../Overdue) and
a visual workflow-stage indicator on each order's detail page.

**Accounting Engine** — every posted journal entry is validated so total
debit == total credit before anything is written; account balances are
always derived live from posted entries, never stored/cached.

**Reports** — Balance Sheet (with as-of date), Profit & Loss (with date
range and Profit Margin), Budget Report (planned vs. actual vs. variance by
analytic account) — all computed from the ledger with a "View Transactions"
drill-down from any account row into the journal entries that produced it.

**Roles** — a 3-role model (Admin, Accountant, Contact) with real Login
ID/password authentication (see Security hardening below) — no OAuth/JWT,
per the prototype's scope, but no faked/hardcoded auth either.

## 3. Architecture

- **Backend**: Python 3.13, FastAPI, Uvicorn.
- **Database**: SQLite (`data/app.db`), created automatically on first run.
- **ORM**: SQLAlchemy 2.0 (declarative models, one `Session` per request).
- **Frontend**: server-rendered Jinja2 templates, plain CSS design system,
  small vanilla-JS snippets for dynamic form rows and live totals — no SPA
  framework.
- **Auth**: Login ID + password (PBKDF2-hashed, salted), a signed session
  cookie (Starlette `SessionMiddleware`), role-based route guards.
- **Business logic**: plain modules under `app/services/` (`tax.py`,
  `accounting.py`, `reports.py`) called directly from routers — no
  repository/interface layers, no microservices.

One application, one database, simple domain services, simple UI, simple
testing — see `docs/IMPLEMENTATION_PLAN.md` for the full rationale and
package layout.

### Security hardening

- **Password storage**: PBKDF2-HMAC-SHA256, 100,000 iterations, unique
  16-byte salt per user, constant-time comparison (`app/security.py`).
- **Secrets**: the session-signing key comes from the `SECRET_KEY`
  environment variable (`app/config.py`), never hardcoded — the app
  refuses to start with a missing key when `ENVIRONMENT=production`.
- **Session cookie**: `SameSite=Strict`, `HttpOnly` (default), `Secure`
  when `ENVIRONMENT=production`, and a bounded lifetime.
- **CSRF**: `SameSite=Strict` cookies plus an Origin/Referer host-match
  check on every state-changing request (`app/main.py`) — a cross-site
  form can't ride an authenticated session.
- **Brute-force protection**: an account locks for `LOGIN_LOCKOUT_MINUTES`
  after `LOGIN_MAX_FAILED_ATTEMPTS` consecutive wrong passwords.
- **Error handling**: unhandled exceptions are logged server-side and shown
  to the user as a generic error page — no stack traces leak to the browser.

## 4. Setup Instructions

Requires Python 3.11+.

```bash
git clone https://github.com/Manish010204/urban-furniture-accounting.git
cd urban-furniture-accounting
pip install -r requirements.txt
```

**Configuration**: copy `.env.example` to `.env` and set a real `SECRET_KEY`
(used to sign session cookies):

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output as SECRET_KEY in .env
```

Without a `.env` file the app still runs locally using an insecure
placeholder key (fine for local development, refused if `ENVIRONMENT=production`
is set without a real `SECRET_KEY` — see `app/config.py`).

## 5. Run Instructions

```bash
python -m uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000** — you'll land on the login page. The
database is created and seeded with demo data automatically on first
startup (see [Seed Data](#seed-data) below). To reset to a clean seeded
state at any time, stop the server and delete `data/app.db`.

## 6. Test Instructions

```bash
python -m pytest -q
```

Runs 40 tests across three files:
- `tests/test_smoke.py` — the app starts, connects to SQLite, every major
  page loads, master data can be created, a full purchase-to-payment
  transaction works, reports render, login/signup/lockout/CSRF/404 behave
  correctly.
- `tests/test_domain.py` — tax calculation, purchase/sales totals,
  debit/credit balance validation, the four core accounting postings,
  P&L, Balance Sheet, and budget variance — all as isolated unit tests
  against an in-memory database.
- `tests/test_e2e.py` — the two critical end-to-end workflows (purchase
  and sales) driven entirely through the HTTP layer, including the Confirm
  step and validation guards (duplicate invoice, overpayment).

## 7. Demo Credentials / Roles

Real Login ID + password authentication (see [Security hardening](#security-hardening)).
Sign in at `/login` with one of the seeded users below, or create a new
Accountant account at `/signup`:

| User | Login ID | Password | Role | Can do |
|---|---|---|---|---|
| Admin User | `admin1` | `Admin@123` | Admin | Create/modify/archive master data, record transactions, view reports |
| Priya Verma | `priya1` | `Priya@123` | Accountant | Create master data, record transactions, view reports (no edit/archive) |
| Nimesh Pathak | `nimesh1` | `Nimesh@123` | Contact | View only their own invoices/bills, make payment |

Use "Sign Out" (top-right) to switch users during a demo.

## 8. Demo Workflow

See **`docs/DEMO_SCRIPT.md`** for the full scripted walkthrough. In short:

1. **Dashboard** — open the Business Command Center, point out the KPI
   cards, Business Pulse, Revenue vs Expenses chart, and Action Center.
2. **Master data** — confirm Azure Furniture (vendor), Nimesh Pathak
   (customer), and Office Chair (product) already exist (seeded).
3. **Purchase**: Purchase Order (Azure Furniture, Office Chair) → Confirm →
   Convert to Vendor Bill → Register payment via Bank.
4. **Sale**: Sales Order (Nimesh Pathak, 5 Office Chairs, with tax) →
   Confirm → Generate Customer Invoice → Register payment via Cash.
5. **Reports**: open Balance Sheet, P&L (drill down "View Transactions" on
   any row), and Budget Report and see both transactions reflected live.

## 9. Seed Data

Seeded automatically on first startup (`app/seed.py`):

- **Contacts**: Azure Furniture (vendor), Nimesh Pathak (customer), Rahul
  Sharma (vendor).
- **Products**: Office Chair, Wooden Table, Sofa, Dining Table, Wooden Chair.
- **Chart of Accounts**: Cash, Bank, Debtors, Creditors, Sales Income,
  Purchases Expense, Tax Payable, Capital.
- **Journals**: Sales Journal, Purchase Journal, Bank Journal, Cash Journal.
- **Analytic Accounts**: Retail Sales (income), Store Operations (expense).
- **Budgets**: Q Retail Sales Budget (₹50,000), Q Store Operations Budget
  (₹20,000).
- **Users**: Admin User, Priya Verma (Accountant), Nimesh Pathak (Contact).
- An opening capital entry (Dr Bank ₹150,000 / Cr Capital ₹150,000) so
  there are funds to pay a vendor bill with in the demo.

## 10. Known Limitations

This is an intentionally simplified prototype:

- No OAuth/SSO/JWT — a one-click demo login stands in for real auth.
- Single flat sales-tax percentage per line, one Tax Payable account — no
  multi-jurisdiction/multi-rate tax engine.
- One vendor bill per Purchase Order and one invoice per Sales Order — no
  partial/split billing.
- No inventory/stock ledger — products carry price/category only.
- No Alembic migrations — the schema is created via
  `Base.metadata.create_all()` on startup.
- No period-close step — the Balance Sheet folds current net profit into a
  live "Retained Earnings" line instead of a formal transfer-to-capital
  journal entry.
- All vendors share one Creditors account and all customers share one
  Debtors account (no per-party sub-ledgers) — per-party detail lives on
  the Vendor Bill / Customer Invoice records themselves.

## 11. Project Structure

```
app/
  main.py              FastAPI app, startup (create tables + seed), router registration
  database.py           SQLAlchemy engine/session
  models.py             All SQLAlchemy models
  auth.py                Session helpers, require_role dependency
  seed.py                Idempotent demo data seeding
  validators.py          Small shared validation helpers
  templating.py           Shared Jinja2Templates instance
  services/
    tax.py                calculate_tax(), calculate_totals()
    accounting.py          create_journal_entry, post_* functions, account balances
    reports.py             balance_sheet, profit_and_loss, budget_report
  routers/                 One module per feature area (contacts, products,
                             accounts, journals, journal_entries,
                             analytic_accounts, budgets, purchases, sales,
                             payments, reports, dashboard, auth)
  templates/               base.html + one folder per module
  static/style.css         The whole design system
tests/
  conftest.py, test_smoke.py, test_domain.py, test_e2e.py
docs/
  REQUIREMENTS.md, IMPLEMENTATION_PLAN.md, DEMO_SCRIPT.md, FINAL_AUDIT.md
  reports/PHASE_*_REPORT.md
requirements.txt
```
