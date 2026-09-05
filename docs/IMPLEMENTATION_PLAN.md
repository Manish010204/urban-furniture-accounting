# Implementation Plan

## Architecture

- **Backend**: Python 3.13, FastAPI, Uvicorn.
- **DB**: SQLite file `data/app.db`, created via `SQLAlchemy` `Base.metadata.create_all()` on
  startup (no migration framework — prototype scope).
- **ORM**: SQLAlchemy 2.0 (declarative models, plain `Session` per-request).
- **Frontend**: Server-rendered Jinja2 templates, one shared base layout, plain CSS
  (no build step), a few `<script>` blocks for interactivity (dynamic SO/PO line rows,
  confirm dialogs). No SPA framework.
- **Auth**: cookie session (`itsdangerous`-signed via Starlette `SessionMiddleware`)
  storing `user_id`; a `/login` page lists demo users to click ("role switcher").
  `require_role(*roles)` FastAPI dependency guards routes.
- **Business logic**: plain Python modules under `app/services/` (`accounting.py`,
  `tax.py`, `reports.py`) called directly from routers — no repository/interface layers.
- **Testing**: `pytest` + FastAPI `TestClient`, a fresh SQLite file per test run via
  fixture, `httpx` for TestClient transport.

## Package layout

```
app/
  main.py              FastAPI app, startup (create tables + seed), router includes
  database.py          engine/session/get_db
  models.py            all SQLAlchemy models
  auth.py              session helpers, require_role dependency, demo users
  seed.py              idempotent demo data seeding
  services/
    tax.py             calculate_tax()
    accounting.py      create_journal_entry, post_* functions, account balances
    reports.py         balance_sheet, profit_and_loss, budget_report
  routers/
    dashboard.py, contacts.py, products.py, accounts.py, journals.py,
    journal_entries.py, analytic_accounts.py, budgets.py,
    purchases.py (PO + Vendor Bill + vendor payment),
    sales.py (SO + Customer Invoice + customer payment),
    reports.py, auth.py
  templates/           base.html + one folder per module
  static/style.css
tests/
  conftest.py
  test_smoke.py
  test_domain.py
  test_e2e.py
docs/
  REQUIREMENTS.md, IMPLEMENTATION_PLAN.md, DEMO_SCRIPT.md, FINAL_AUDIT.md
  reports/PHASE_*_REPORT.md
requirements.txt
README.md
.gitignore
```

## Phase plan (as mandated by the task)

0. Repository + requirement analysis (this document + REQUIREMENTS.md). ✅ current phase
1. Project foundation: FastAPI app skeleton, DB, base layout, nav, pytest setup, smoke test app starts.
2. Master data: Contacts, Products, Chart of Accounts, Journals, Analytic Accounts, Budgets — full CRUD + archive + seed data.
3. Accounting engine: JournalEntry/Lines, debit=credit validation, balance calc, posting rules for the 4 core transactions.
4. Purchase flow: PO → Vendor Bill → Payment, UI + accounting effects + tests.
5. Sales flow: SO → Customer Invoice (with tax) → Payment, UI + accounting effects + tests.
6. Reporting: Balance Sheet, P&L, Budget Report — all computed from DB.
7. Dashboard + UI polish: summary cards, badges, empty states, responsive layout.
8. Complete system test: full pytest run + manual walkthrough of every page + the two demo flows.
9. Final demo prep: README, DEMO_SCRIPT.md, final full test run.

Final: FINAL_AUDIT.md cross-checking every requirement row in REQUIREMENTS.md.

## Data model notes

- `Contact(id, name, type[customer/vendor/both], email, mobile, city, state, pincode,
  profile_image_path, is_archived, linked_user_id nullable)`
- `Product(id, name, type[goods/service/combo], sales_price, cost_price, category, is_archived)`
- `Account(id, name, type[asset/liability/income/expense/capital], code)` — balance is derived,
  not stored, to avoid drift.
- `Journal(id, name, type[sales/purchase/bank/cash], default_debit_account_id, default_credit_account_id)`
- `JournalEntry(id, journal_id, date, reference, source_type, source_id)` + `JournalEntryLine(id,
  entry_id, account_id, debit, credit, analytic_account_id nullable)`
- `AnalyticAccount(id, name, type[income/expense])`
- `Budget(id, name, period_start, period_end, responsible_person, planned_amount, analytic_account_id)`
- `PurchaseOrder(id, vendor_id, date, status)` + `PurchaseOrderLine(id, po_id, product_id, qty, unit_price)`
- `VendorBill(id, purchase_order_id, vendor_id, invoice_date, due_date, total, status[unpaid/paid], journal_entry_id)`
- `SalesOrder(id, customer_id, date, status)` + `SalesOrderLine(id, so_id, product_id, qty, unit_price, tax_percent)`
- `CustomerInvoice(id, sales_order_id, customer_id, invoice_date, due_date, subtotal, tax_amount, total, status, journal_entry_id)`
- `Payment(id, direction[in/out], party_contact_id, method[cash/bank], amount, date, vendor_bill_id
  nullable, customer_invoice_id nullable, journal_entry_id)`
- `User(id, name, role[admin/accountant/contact], contact_id nullable)`

## Explicit simplifications (documented, not hidden)

- Account "current balance" is computed on read by summing `JournalEntryLine` debit/credit —
  simple and always correct, avoids a stored-balance drift bug class.
- One invoice/bill per PO/SO (no partial/multiple conversion) — matches spec's linear workflow diagram.
- Tax is a single flat percentage per sales line, posted to one `Tax Payable` liability account.
- No inventory/stock ledger — Products carry price/category only, per spec's field list.
