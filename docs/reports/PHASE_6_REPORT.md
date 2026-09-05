# Phase 6 Report

## Objective
Implement Balance Sheet, Profit & Loss, and Budget Report, all computed
live from posted journal entries — nothing hardcoded.

## Implementation (`app/services/reports.py`, `app/routers/reports.py`, `templates/reports/*`)

### Balance Sheet (`/reports/balance-sheet?as_of=YYYY-MM-DD`)
Sums every non-archived Asset/Liability/Capital account's balance as of the
given date (defaults to today) by filtering `JournalEntryLine` joined to
`JournalEntry.date <= as_of`. Net profit for the same period (from the P&L
function) is folded in as "Retained Earnings" so the sheet always balances:
`Total Assets == Total Liabilities + Total Capital (incl. retained
earnings)` — verified in `test_balance_sheet_stays_balanced` and manually
via the HTTP walkthrough (₹145,625 = ₹145,625 after the demo purchase +
sale).

### Profit & Loss (`/reports/profit-loss?since=&as_of=`)
Sums every Income/Expense account's balance, optionally bounded by a
`since`/`as_of` date range. `net_profit = total_income - total_expenses`.

### Budget Report (`/reports/budget`)
For each `Budget`, sums the `JournalEntryLine`s tagged with that budget's
`analytic_account_id` and dated within `[period_start, period_end]` —
income analytic accounts sum `credit - debit`, expense ones sum
`debit - credit`. `variance = planned_amount - actual`. This is also reused
by the Budgets list page (Phase 2) so the budget list itself doubles as a
live report.

Analytic tagging happens at the Purchase Order / Sales Order level (an
optional `analytic_account_id` field, added in this phase's model work) and
flows through to the posted journal entry's expense/income line in
`post_vendor_bill()` / `post_customer_invoice()`.

## Tests
- `tests/test_domain.py::test_profit_and_loss_reflects_postings`
- `tests/test_domain.py::test_balance_sheet_stays_balanced`
- `tests/test_domain.py::test_budget_variance_calculation`
- `tests/test_smoke.py::test_reports_render_with_data`
- `tests/test_e2e.py` — both end-to-end tests assert the reports reflect
  their transactions.

## Test Results (first full run, Phases 1-6)
```
$ python -m pytest -q
........................                                            [100%]
24 passed, 83 warnings in 6.17s
```
All warnings are deprecation notices (SQLAlchemy `datetime.utcnow()`,
FastAPI `on_event`, Starlette `TemplateResponse` argument order) — none
affect correctness; noted as a Known Limitation below rather than fixed now
to avoid scope creep.

## Manual Verification
Walked the full demo through raw HTTP calls (bypassing the browser) against
the seeded app:
1. Purchase Order (Azure Furniture, 10 Office Chairs @ ₹2,800) → Vendor
   Bill → paid in full via Bank.
2. Sales Order (Nimesh Pathak, 5 Office Chairs @ ₹4,500, 5% tax) → Customer
   Invoice → paid in full via Cash.
3. Balance Sheet: Cash ₹23,625 / Bank ₹122,000 / Debtors ₹0 / Total Assets
   ₹145,625 = Creditors ₹0 + Tax Payable ₹1,125 + Capital ₹150,000 +
   Retained Earnings −₹5,500 = ₹145,625. Balanced.
4. P&L: Sales Income ₹22,500, Purchases Expense ₹28,000, Net Profit
   −₹5,500 (expected — one bought-in bulk purchase against one smaller
   sale in this manual smoke run).
5. Budget Report: renders correctly; actual shows ₹0 for that manual run
   because no analytic account was attached to that ad-hoc PO/SO — the
   `test_budget_variance_calculation` unit test separately proves the
   actual/variance math itself is correct when an analytic account *is*
   attached, and the seed data's own budgets are wired to the seeded
   analytic accounts for the scripted demo (see `docs/DEMO_SCRIPT.md`).

## Git Commit
`e261d9f` (shared — see Phase 1 report).

## Known Limitations
- Deprecation warnings noted above (non-breaking).
- Balance Sheet's "Retained Earnings" is a live-computed convenience line
  rather than a formal period-close/transfer-to-capital step — acceptable
  simplification for a prototype demo.

## Next Phase
Phase 7 — Dashboard + UI Polish.
