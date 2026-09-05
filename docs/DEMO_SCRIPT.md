# Demo Script (5-10 minutes)

Goal: show the complete accounting workflow —
**Master Data → Purchase → Vendor Bill → Payment → Accounting**, then
**Master Data → Sale → Customer Invoice → Payment → Accounting**, then
**Reports** — using data that's already populated so the app looks alive
from the first click.

Start the app fresh so the seed data is in place and the numbers below
match exactly:

```bash
rm -f data/app.db     # optional — only if you've run the demo before
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**.

## 0. Login / Roles (30 sec)

- On the login page, click **Sign in** next to **Admin User**.
- Point out the role list: Admin, Accountant, Contact — mention "Switch
  User" (top right) lets you jump roles instantly for the demo without a
  password, since this is a prototype.

## 1. Master Data (1 min)

- **Contacts**: already has Azure Furniture (vendor), Nimesh Pathak
  (customer), Rahul Sharma (vendor). Open Nimesh Pathak's detail page to
  show the record (city/state/pincode, active status).
- **Products**: Office Chair, Wooden Table, Sofa, Dining Table, Wooden
  Chair — open Office Chair to show sales price ₹4,500 / cost price
  ₹2,800.
- **Chart of Accounts**: point out Cash, Bank, Debtors, Creditors, Sales
  Income, Purchases Expense, Tax Payable, Capital — each with a **live
  balance** (Bank already shows ₹150,000 from the seeded opening capital).

## 2. Purchase Flow — Azure Furniture (2 min)

1. **Purchases → New Purchase Order.**
   - Vendor: **Azure Furniture**
   - Product: **Office Chair**, Quantity **10**, Unit Price **2800**
     (auto-filled from the product's cost price)
   - Analytic Account: **Store Operations** (optional, but pick it so the
     Budget Report below shows a real actual/variance)
   - Save → PO total shows **₹28,000**.
2. On the PO detail page, click **Convert to Vendor Bill**.
   - Invoice Date / Due Date → accept the defaults, Create.
   - Point out the bill total (₹28,000) matches the PO exactly.
3. On the Vendor Bill page, click **Register Payment**.
   - Method: **Bank**, amount defaults to the full ₹28,000. Submit.
   - Status flips to **Paid**.
4. **Show the accounting effect**: open the linked Journal Entry (link on
   the bill page) — Debit Purchases Expense ₹28,000 / Credit Creditors
   ₹28,000 for the bill, and a second entry for the payment: Debit
   Creditors ₹28,000 / Credit Bank ₹28,000. Both balanced.
5. Open **Chart of Accounts** — Bank has dropped to **₹122,000**, Creditors
   is back to **₹0**.

## 3. Sales Flow — Nimesh Pathak (2 min)

1. **Sales → New Sales Order.**
   - Customer: **Nimesh Pathak**
   - Product: **Office Chair**, Quantity **5**, Unit Price **4500**
     (auto-filled), Tax % **5** (default)
   - Analytic Account: **Retail Sales**
   - Watch the live totals: Subtotal ₹22,500, Tax ₹1,125, **Grand Total
     ₹23,625**. Save.
2. On the SO detail page, click **Generate Customer Invoice**.
   - Accept the date defaults, Create — point out the invoice preserves
     customer/product/qty/price/tax/total exactly.
3. On the invoice page, click **Receive Payment**.
   - Method: **Cash**, amount defaults to ₹23,625. Submit.
   - Status flips to **Paid**.
4. **Show the accounting effect**: Debit Debtors ₹23,625 / Credit Sales
   Income ₹22,500 / Credit Tax Payable ₹1,125 for the invoice; Debit Cash
   ₹23,625 / Credit Debtors ₹23,625 for the payment.
5. Open **Chart of Accounts** — Cash now shows **₹23,625**, Debtors is back
   to **₹0**, Tax Payable shows **₹1,125**.

## 4. Reports (2 min)

- **Reports → Balance Sheet**: Assets (Cash ₹23,625 + Bank ₹122,000 +
  Debtors ₹0 = **₹145,625**) exactly equal Liabilities + Capital
  (Creditors ₹0 + Tax Payable ₹1,125 + Capital ₹150,000 + Retained
  Earnings −₹5,500 = **₹145,625**). Point out this is computed live from
  the two transactions just entered, not hardcoded.
- **Reports → Profit & Loss**: Sales Income ₹22,500, Purchases Expense
  ₹28,000, Net Profit **−₹5,500** — explain this single demo run bought
  more than it sold (10 chairs in, 5 out), which is exactly what the
  numbers should show; in a longer-running dataset the margin recovers as
  more sales are recorded.
- **Reports → Budget Report**: because the PO/SO above were tagged with
  Store Operations / Retail Sales, the Q Retail Sales Budget shows
  **Actual ₹22,500** against its ₹50,000 plan (variance ₹27,500), and the
  Q Store Operations Budget shows **Actual ₹28,000** against its ₹20,000
  plan (variance −₹8,000, i.e. over budget) — both computed from the
  analytic-tagged postings, not hardcoded.

## 5. Roles, quickly (1 min, optional)

- **Switch User → Nimesh Pathak (Contact)**: the sidebar collapses to "My
  Invoices & Bills" — only their own invoice is visible, with a "Make
  Payment" action. Try navigating directly to `/contacts` — redirected
  home, proving the role guard works.
- **Switch User → Priya Verma (Accountant)**: full navigation is back, but
  opening a contact and trying to Edit — redirected with a permission
  message, since only Admin can modify/archive master data per the spec's
  role table.

## Wrap-up

That's the full loop: **Master Data → Transaction → Bill/Invoice → Payment
→ Journal Entry → Account Balances → Reports**, end to end, with every
number traceable back to an actual posted journal entry.
