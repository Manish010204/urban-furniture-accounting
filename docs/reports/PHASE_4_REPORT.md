# Phase 4 Report

## Objective
Implement the complete Purchase Order → Vendor Bill → Payment → Journal
Entry workflow end-to-end through the UI.

## Purchase Workflow (`app/routers/purchases.py`, `templates/purchases/*`)
1. **Create Purchase Order** (`/purchases/new`): pick an active (non-archived)
   vendor, add one or more product lines with quantity and unit price
   (auto-filled from the product's cost price, editable), optional analytic
   account. Client-side JS recalculates the line/order totals live; server
   re-validates quantity > 0, price >= 0, and that vendor/products are not
   archived.
2. **Purchase Order detail** (`/purchases/{id}`): shows lines and total,
   with a "Convert to Vendor Bill" action (hidden once a bill already
   exists — enforces one bill per PO).
3. **Convert to Vendor Bill** (`/purchases/{id}/convert`): prompts for
   invoice date and due date, then creates the `VendorBill` (copying
   vendor, total, and the PO link), posts the accounting entry via
   `post_vendor_bill()`, and marks the PO `billed`.
4. **Register vendor payment** (`/purchases/bills/{id}/pay`): choose Cash or
   Bank and an amount (defaulting to, and capped at, the outstanding
   balance); posts `post_vendor_payment()` and recomputes the bill's status
   (`unpaid` → `partially_paid` → `paid`) from the actual sum of payments
   against it (not a cached counter, to avoid drift).

## Accounting Entries Generated (worked example — Azure Furniture)
PO: 10 × Office Chair @ ₹2,800 = ₹28,000.
- Vendor Bill posted: **Dr Purchases Expense 28,000 / Cr Creditors 28,000**.
- Bank payment of ₹28,000: **Dr Creditors 28,000 / Cr Bank 28,000**.
- Verified manually via HTTP walkthrough: Bank balance dropped from the
  seeded ₹150,000 opening balance to ₹122,000; Creditors returned to ₹0;
  bill status became `paid`.

## Validation / Guards
- Archived vendor/products cannot be selected (excluded from dropdowns,
  re-checked on submit).
- A PO cannot be converted to a bill twice (`po.bill` existence check).
- A payment cannot exceed the outstanding amount, and a fully-paid bill
  cannot be paid again (both return a validation error and re-render the
  form instead of silently failing).
- Contact-role users can view and pay only bills where `bill.vendor_id`
  matches their own linked contact.

## Tests
- `tests/test_smoke.py::test_create_transaction_generate_bill_and_register_payment`
- `tests/test_e2e.py::test_end_to_end_purchase_flow` — creates a vendor and
  product, creates a PO, converts to a bill, verifies the total, pays it in
  full via Bank, and confirms the linked journal entry is balanced.

## Test Results
24/24 passing (full suite, reported in Phase 8).

## Git Commit
`e261d9f` (shared — see Phase 1 report).

## Known Limitations
One vendor bill per purchase order (no partial/split billing) — matches the
spec's linear workflow diagram.

## Next Phase
Phase 5 — Sales Flow.
