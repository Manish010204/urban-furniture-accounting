# Requirements Traceability — Urban Furniture Accounting System

Source: hackathon specification supplied in the task prompt. No separate mockup image file
was found in the repository at the start of Phase 0 (the repo was empty — only `.git`);
the "visual mockup/reference" is therefore treated as the textual UI/UX section of the
spec (sidebar items, dashboard cards, table/form conventions) and a generic modern
accounting-dashboard look (cards, tables, status badges) is used as the visual target.

Legend: ✅ planned to implement in this prototype, ⏭ explicitly out of scope (per spec's
"do not over-engineer" guidance), with reasoning.

## Roles / Auth

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Admin/Business Owner role | full CRUD + transactions + reports | `User.role = admin`, permission checks in routers | smoke: admin can reach all pages |
| Invoicing User/Accountant role | create master data, record transactions, view reports (no archive) | `User.role = accountant` | smoke: role switch works |
| Contact role | view own invoices/bills, make payment only | `User.role = contact`, linked to `Contact` row, filtered queries | domain: contact user cannot see others' invoices |
| Simple login/role switcher | no OAuth/JWT | cookie-session login page listing demo users, `require_role` dependency | smoke: login page loads, login sets session |

## Master Data

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Contact: name/type/email/mobile/address/profile image | Contact master | `Contact` model + CRUD routes/templates | domain: create/validate contact |
| Contact list/search/filter/create/edit/archive/details | Contact UI | `/contacts` router + templates, `is_archived` flag | smoke: list & create |
| Product: name/type/sales price/cost price/category | Product master | `Product` model + CRUD | domain: create/validate product |
| Product list/search/filter/create/edit/archive/details | Product UI | `/products` router + templates | smoke: list & create |
| Chart of Accounts: name/type, seed accounts | Account master | `Account` model (type enum Asset/Liability/Income/Expense/Capital) + CRUD + balance calc | domain: balance calculation |
| COA UI: list/create/edit/type/current balance | Account UI | `/accounts` router + templates showing computed balance | smoke: list loads |
| Journals: name/type/default accounts, 4 seeded journals | Journal master | `Journal` model + CRUD | smoke: list & seed present |
| Journal Entries: journal/date/reference/lines/account/debit/credit | JournalEntry + JournalEntryLine | models + posting service | domain: balanced/unbalanced validation |
| Double-entry: debit==credit enforced | Accounting engine | `accounting.py` validates before insert/commit | domain: 100/100 valid, 100/90 invalid |
| Analytic Account: name/type (income/expense) | AnalyticAccount master | model + minimal CRUD | domain: create + link to budget |
| Budget: name/period/responsible person/planned amount/analytic account | Budget master | model + CRUD + budget report | domain: variance calc |

## Transactions

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Purchase Order: vendor/product/qty/unit price, workflow | PurchaseOrder + lines | model + form + total calc | domain: PO total calculation |
| Convert PO → Vendor Bill preserving PO info | VendorBill | conversion route copies PO data, links `purchase_order_id` | domain: conversion preserves data |
| Vendor Bill: invoice date/due date/register payment | VendorBill fields + payment route | model fields + `/purchases/bills/{id}/pay` | e2e: bill → payment |
| Sales Order: customer/product/qty/unit price/tax | SalesOrder + lines | model + form + tax calc | domain: sales total + tax |
| Generate Customer Invoice from SO preserving data | CustomerInvoice | conversion route | domain: invoice preserves SO data |
| Customer Invoice: receive payment cash/bank | CustomerInvoice + payment route | model + `/sales/invoices/{id}/pay` | e2e: invoice → payment |
| Payment against Vendor Bill / Customer Invoice, method cash/bank | Payment model | model + accounting journal creation | domain: payment accounting effect |
| Payment creates journal entry | Accounting engine | `post_vendor_payment` / `post_customer_payment` | domain: balances update |

## Tax

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Tax % on sales, subtotal/tax/grand total, deterministic | Tax calc | `tax.py: calculate_tax()` pure function used by Sales Order/Invoice | domain: tax calculation unit test |

## Accounting Logic

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Customer sale: Dr Debtors / Cr Sales Income (+Tax Payable) | posting rule | `post_customer_invoice()` | domain: invoice posting balanced & correct accounts |
| Customer payment: Dr Cash/Bank / Cr Debtors | posting rule | `post_customer_payment()` | domain: payment posting |
| Vendor bill: Dr Purchases Expense / Cr Creditors | posting rule | `post_vendor_bill()` | domain: bill posting |
| Vendor payment: Dr Creditors / Cr Cash/Bank | posting rule | `post_vendor_payment()` | domain: payment posting |
| Every entry balanced | invariant | assertion in `create_journal_entry()` | domain: unbalanced entry rejected |

## Reports

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Balance Sheet: Assets/Liabilities/Capital from data | report | `reports.py: balance_sheet()` sums `JournalEntryLine` by account type | domain: balance sheet totals match postings |
| P&L: sales/purchases/expenses/net profit from data | report | `reports.py: profit_and_loss()` | domain: P&L matches postings |
| Budget report: budget/period/responsible/analytic/planned/actual/variance | report | `reports.py: budget_report()` sums actual from analytic-tagged journal lines | domain: variance calc |
| Period/date filtering | report | optional `as_of`/date-range query params | smoke: report page loads with & without filter |

## Demo Data

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Seed contacts/products/accounts/journals | `seed.py` | run at startup if DB empty | smoke: dashboard shows non-zero data |

## Validation

| Requirement | Feature | Planned Implementation | Planned Test |
|---|---|---|---|
| Required fields, qty>0, price>=0, tax>=0, email/pincode format | form validation | Pydantic-style manual checks + HTML `required` | domain: invalid inputs rejected |
| Archived contacts/products not selectable for new transactions | archive guard | query filters `is_archived=False` in selection dropdowns + server check | domain: archived contact rejected in new PO |
| Journal entries must balance | see above | see above | see above |
| Payment cannot exceed outstanding; no pay on fully-paid doc; no duplicate invoice from same SO | transaction guards | checks in payment/invoice routes | domain: overpayment rejected, duplicate invoice rejected |

## Testing

| Requirement | Feature | Planned Implementation |
|---|---|---|
| Smoke tests (start, DB, pages, CRUD, transaction, invoice/bill, payment, reports) | `tests/test_smoke.py` | pytest + FastAPI TestClient, isolated SQLite file per test session |
| Domain tests (tax, totals, debit/credit validation, posting effects, P&L, balance sheet, budget variance, e2e flows) | `tests/test_domain.py`, `tests/test_e2e.py` | pytest, direct service-layer calls |

## Explicitly out of scope (⏭)

- OAuth/SSO/JWT — spec explicitly forbids, simple cookie session used instead.
- Multi-currency, multi-company, tax jurisdictions — spec asks for a single simple tax %.
- Inventory/stock valuation, partial deliveries — not mentioned in spec; PO/SO track price & qty only.
- Recurring invoices, credit notes, multi-level approvals — not in spec.
- Alembic migrations — prototype uses `Base.metadata.create_all` on startup instead of a migration framework (spec explicitly allows "simple prototype database initialization").
