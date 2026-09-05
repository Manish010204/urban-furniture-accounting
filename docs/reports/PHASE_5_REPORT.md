# Phase 5 Report

## Objective
Implement the complete Sales Order → Customer Invoice → Payment → Journal
Entry workflow, including tax.

## Sales Workflow (`app/routers/sales.py`, `templates/sales/*`)
1. **Create Sales Order** (`/sales/new`): pick an active customer, add
   product lines with quantity, unit price (auto-filled from the product's
   sales price), and a per-line tax percent (defaults to 5%). JS live-updates
   subtotal / tax / grand total as the user types; server re-validates
   qty > 0, price >= 0, tax >= 0, and that customer/products are active.
2. **Sales Order detail**: shows the line breakdown plus subtotal, tax, and
   grand total; "Generate Customer Invoice" action (hidden once an invoice
   already exists for this order — enforces one invoice per SO, and a
   direct hit on the generate route for an already-invoiced order returns
   an explicit "already exists" error rather than silently duplicating).
3. **Generate Customer Invoice**: prompts for invoice/due date, copies
   customer, subtotal, tax_amount and total from the SO, posts
   `post_customer_invoice()` (Debtors / Sales Income / Tax Payable), marks
   the SO `invoiced`.
4. **Register customer payment**: Cash or Bank, amount capped at the
   outstanding balance; posts `post_customer_payment()` and recomputes
   invoice status the same way vendor bills do (summed from actual
   payments, not a cached field).

## Worked Example (Nimesh Pathak, 5 Office Chairs)
5 × ₹4,500 = ₹22,500 subtotal, 5% tax = ₹1,125, total ₹23,625.
- Invoice posted: **Dr Debtors 23,625 / Cr Sales Income 22,500 / Cr Tax
  Payable 1,125**.
- Cash payment of ₹23,625: **Dr Cash 23,625 / Cr Debtors 23,625**.
- Verified via HTTP walkthrough: Cash balance rose to ₹23,625, Debtors
  returned to ₹0, invoice status became `paid`.

## Tax
`app/services/tax.py` — `calculate_tax()` and `calculate_totals()` are pure,
deterministic functions (`subtotal * tax_percent / 100`, rounded to 2
decimals) with no per-jurisdiction logic, per the spec's "simple tax
mechanism" instruction. The same functions back both the SO line total
property and the unit tests.

## Validation / Guards
Same pattern as Purchases: archived customer/products rejected, duplicate
invoice generation rejected, overpayment rejected, paying an already-paid
invoice rejected, contact-role users restricted to their own invoices.

## Tests
- `tests/test_domain.py::test_tax_calculation_basic`,
  `test_calculate_totals_matches_subtotal_tax_grand_total`,
  `test_sales_order_total_calculation_with_tax`,
  `test_customer_invoice_posting_creates_expected_accounting_effect`,
  `test_customer_payment_posting_creates_expected_accounting_effect`.
- `tests/test_e2e.py::test_end_to_end_sales_flow` — creates a customer and
  product, creates an SO with tax, generates the invoice, confirms
  duplicate-invoice rejection, pays in full via Cash, confirms
  double-payment rejection, and checks the reports reflect it.

## Test Results
24/24 passing (full suite, reported in Phase 8).

## Git Commit
`e261d9f` (shared — see Phase 1 report).

## Known Limitations
Tax is a single flat percentage per line posted to one Tax Payable account
— no multi-rate/multi-jurisdiction tax engine, per spec.

## Next Phase
Phase 6 — Reporting.
