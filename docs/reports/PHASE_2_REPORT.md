# Phase 2 Report

## Objective
Implement all six master-data modules with CRUD, archive, validation, and
seed data. (See the Phase 1 report for why Phases 1-6 share one commit.)

## Implementation

### Contacts (`app/routers/contacts.py`, `templates/contacts/*`)
Fields: name, type (customer/vendor/both), email, mobile, city, state,
pincode, is_archived. List with search (`q`) + type filter + show-archived
toggle; create/edit/detail pages; archive toggles `is_archived` rather than
deleting the row. Validation: name required, email format, pincode format
(`app/validators.py`).

### Products (`app/routers/products.py`, `templates/products/*`)
Fields: name, type (goods/service/combo), sales_price, cost_price, category,
is_archived. Same list/search/create/edit/detail/archive pattern as Contacts.
Validation: name required, prices >= 0.

### Chart of Accounts (`app/routers/accounts.py`, `templates/accounts/*`)
Fields: name, type (asset/liability/income/expense/capital), code. List
shows each account's **current balance**, computed live via
`services.accounting.account_balance()` (never stored, so it can never
drift from postings). Create/edit forms.

### Journals (`app/routers/journals.py`, `templates/journals/*`)
Fields: name, type (sales/purchase/bank/cash), default debit/credit account.
Four are seeded: Sales Journal, Purchase Journal, Bank Journal, Cash
Journal.

### Journal Entries (`app/routers/journal_entries.py`, `templates/journal_entries/*`)
Manual entry form with dynamic add/remove line rows (account, debit,
credit); server-side rejects entries with fewer than 2 lines or where total
debit != total credit (delegates to the Phase 3 accounting engine). List
shows every entry with a Balanced/Unbalanced badge; detail page shows the
full line breakdown.

### Analytic Accounts (`app/routers/analytic_accounts.py`)
Fields: name, type (income/expense). Minimal list + create, per spec's
"implement only the minimum required functionality."

### Budgets (`app/routers/budgets.py`, `templates/budgets/*`)
Fields: name, period_start, period_end, responsible_person, planned_amount,
analytic_account. List page doubles as the live budget report (planned /
actual / variance), detail page shows one budget.

## Validations Implemented
Required fields, price/amount >= 0, email format, pincode format, archived
contacts/products excluded from vendor/customer/product dropdowns in
Purchase/Sales Order forms (enforced both by excluding them from the
dropdown query and by re-checking `is_archived` server-side on submit).

## Seed Data (`app/seed.py`)
- Accounts: Cash, Bank, Debtors, Creditors, Sales Income, Purchases Expense,
  Tax Payable, Capital.
- Journals: Sales Journal, Purchase Journal, Bank Journal, Cash Journal.
- Contacts: Azure Furniture (vendor), Nimesh Pathak (customer), Rahul Sharma
  (vendor).
- Products: Office Chair, Wooden Table, Sofa, Dining Table, Wooden Chair.
- Analytic Accounts: Retail Sales (income), Store Operations (expense).
- Budgets: Q Retail Sales Budget (₹50,000), Q Store Operations Budget
  (₹20,000), both tied to the analytic accounts above.
- Users: Admin User, Priya Verma (Accountant), Nimesh Pathak (Contact).
- An opening capital journal entry (Dr Bank ₹150,000 / Cr Capital ₹150,000)
  so the Bank account has funds to demonstrate a vendor payment.

## Tests
`tests/test_smoke.py::test_seed_data_present_on_dashboard_and_lists`,
`test_all_major_pages_load`, `test_create_and_read_contact`.

## Test Results
See Phase 8 report for the consolidated final run; 24/24 passing as of this
increment.

## Git Commit
`e261d9f` (shared — see Phase 1 report).

## Known Limitations
Journals/Analytic Accounts/Budgets do not have an archive toggle in the UI
(only Contacts and Products do) — the spec's explicit archive requirement
was scoped to those two modules.

## Next Phase
Phase 3 — Accounting Engine.
