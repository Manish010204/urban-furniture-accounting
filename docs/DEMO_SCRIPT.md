# Demo Script (5-10 minutes)

Goal: show the complete accounting workflow —
**Business Command Center → Master Data → Purchase → Confirm → Vendor Bill
→ Payment → Accounting**, then
**Master Data → Sale → Confirm → Customer Invoice → Payment → Accounting**,
then **Reports** — on top of ~5 months of real seeded history, so the app
looks alive and lived-in from the first click instead of an empty shell.

> **Numbers below are illustrative, not exact.** The seed data is generated
> relative to whatever day the app first starts (`date.today()`), so exact
> rupee figures and dates will differ from this doc every time — that's
> expected. Read whatever the screen actually shows; don't insist it match
> a number printed here. If asked why, that's a good thing to say out loud:
> it proves the numbers are computed live, not hardcoded to match a script.

```bash
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. (Only delete `data/app.db` first if you
specifically want a fresh reseed — the existing one already has a full
history built up and is fine to demo from as-is.)

## 0. Login / Roles (30 sec)

- On the login page, sign in as **Admin User** (Login ID `admin1`, password
  `Admin@123`) — real authentication: hashed password, signed session
  cookie, account lockout after repeated failed attempts.
- Mention the **Sign Up** link creates a real Accountant account on the
  spot (with live validation — unique Login ID, unique email, password
  complexity) if you want to show that flow.
- Point out the role list: Admin, Accountant, Contact — use "Sign Out"
  (top right) to switch users during the demo.

## 1. Business Command Center (1 min)

- Point out the **KPI cards** — Revenue/Expenses/Net Profit *this month*
  with a trend arrow vs. last month (plus an all-time figure underneath),
  Cash+Bank, Receivables, Payables. Every number is live from the ledger.
- **Business Pulse** — Profitability / Cash Position / Collections / Budget
  Control, each a plain-English label backed by a real calculated ratio
  (net margin, payables cover ratio, collection rate, budget utilization) —
  not an arbitrary score.
- **Revenue vs Expenses** — a genuine 6-month trend with real variation
  month to month (plain inline SVG, no charting library).
- **Action Center** — dynamically generated from real data. You should see
  several real items here: an overdue vendor bill, an overdue customer
  invoice, a bill due soon, and orders still sitting in Draft. Point out
  that none of this is fabricated — each line links straight to the record
  it's describing.

## 2. Master Data (1 min)

- **Contacts**: Azure Furniture and Rahul Sharma (vendors), Nimesh Pathak
  and Kavya Interiors (customers). Open Nimesh Pathak's detail page to
  show the 360° view (Total Sales/Paid/Outstanding/Overdue) built from his
  real multi-month order history.
- **Products**: Office Chair, Wooden Table, Sofa, Dining Table, Wooden
  Chair — open Office Chair to show sales price ₹4,500, cost price ₹2,800,
  and the computed **Gross Margin** (₹1,700 — fixed, since margin is just
  sales price minus cost price, independent of how much has sold).
- **Chart of Accounts**: point out Cash, Bank, Debtors, Creditors, Sales
  Income, Purchases Expense, Tax Payable, Capital — each with a **live
  balance**, built up from every posted journal entry so far, not a single
  opening figure.

## 3. Purchase Flow — live, on top of existing history (2 min)

1. **Purchase → Purchase Order → New Purchase Order.**
   - Vendor: **Azure Furniture**
   - Product: **Office Chair**, Quantity **10**, Unit Price **2800**
   - Budget Analytics: **Store Operations** (optional, but pick it so the
     Budget Report below reflects this new spend against the plan)
   - Save → PO total shows **₹28,000**, status **Draft**.
2. On the PO detail page, note the workflow pipeline (Draft → Confirmed →
   Vendor Bill → Paid). Click **Confirm** — status moves to Confirmed.
3. Click **Create Bill** (was "Convert to Vendor Bill").
   - Invoice Date / Due Date → accept the defaults, Create.
   - Point out the bill total (₹28,000) matches the PO exactly.
4. On the Vendor Bill page, click **Register Payment**.
   - Method: **Bank**, amount defaults to the full ₹28,000. Submit.
   - Status flips to **Paid**; the workflow pipeline on the PO now shows
     every stage complete.
5. **Show the accounting effect**: open the linked Journal Entry (link on
   the bill page) — Debit Purchases Expense ₹28,000 / Credit Creditors
   ₹28,000 for the bill, and a second entry for the payment: Debit
   Creditors ₹28,000 / Credit Bank ₹28,000. Both balanced, and the Partner
   column shows Azure Furniture.
6. Open **Chart of Accounts** — Bank has dropped by exactly ₹28,000 from
   whatever it showed before this step; Creditors nets back to where it
   was (it was only briefly ₹28,000 higher, between steps 3 and 4).

## 4. Sales Flow — Nimesh Pathak (2 min)

1. **Sales → Sales Order → New Sales Order.**
   - Customer: **Nimesh Pathak**
   - Product: **Office Chair**, Quantity **5**, Unit Price **4500**
     (auto-filled), Tax % **5** (default)
   - Budget Analytics: **Retail Sales**
   - Watch the live totals: Subtotal ₹22,500, Tax ₹1,125, **Grand Total
     ₹23,625**. Save → status **Draft**.
2. Click **Confirm**, then **Create Invoice** (was "Generate Customer
   Invoice").
   - Accept the date defaults, Create — point out the invoice preserves
     customer/product/qty/price/tax/total exactly.
3. On the invoice page, click **Receive Payment**.
   - Method: **Cash**, amount defaults to ₹23,625. Submit.
   - Status flips to **Paid**.
4. **Show the accounting effect**: Debit Debtors ₹23,625 / Credit Sales
   Income ₹22,500 / Credit Tax Payable ₹1,125 for the invoice; Debit Cash
   ₹23,625 / Credit Debtors ₹23,625 for the payment.
5. Open **Chart of Accounts** — Cash and Sales Income both moved up by
   exactly this transaction's amounts from whatever they showed before.
6. Back on the **Sales** page, show the status filter chips (All/Draft/
   Confirmed/Invoiced/... and Not Paid/Partially Paid/Paid/Overdue on the
   invoices table below) — point out there are already real rows in
   several of these states from the seeded history, not just the one you
   just created.

## 4b. Print / Download (30 sec, optional but easy points)

- On the Vendor Bill or Customer Invoice page you just created, click
  **🖨 Print / Download PDF**. Show the clean printable layout (nav and
  buttons hidden, a document header with the bill/invoice number and
  timestamp) — choosing "Save as PDF" in the browser's print dialog gives
  a real downloadable document. Same feature exists on all three reports.

## 5. Reports (2 min)

- **Reports → Balance Sheet**: Assets exactly equal Liabilities + Capital
  — that's the one number relationship that must always hold, regardless
  of how much history exists. Click **View Transactions** next to any row
  to drill down into the journal entries behind that number.
- **Reports → Profit & Loss**: Sales Income, Purchases Expense, Net Profit,
  and Profit Margin — all computed from the date range shown, live.
- **Reports → Budget Report**: the Q Retail Sales Budget (₹90,000 plan) and
  Q Store Operations Budget (₹60,000 plan) both show real Actual amounts
  and a visual progress bar, computed from every analytic-tagged posting
  in the current month — including the transaction you just created above.

## 6. Roles, quickly (1 min, optional)

- **Sign Out, sign in as Nimesh Pathak** (`nimesh1` / `Nimesh@123`, Contact
  role): lands on "My Financial Portal" — total/paid/unpaid/overdue invoice
  counts and outstanding amount, then their own invoice list only, with a
  "Make Payment" action. Try navigating directly to `/contacts` —
  redirected home, proving the role guard works.
- **Sign in as Priya Verma** (`priya1` / `Priya@123`, Accountant): full
  navigation is back, but opening a contact and trying to Edit —
  redirected with a permission message, since only Admin can modify/archive
  master data per the spec's role table.

## Wrap-up

That's the full loop: **Business Command Center → Master Data →
Transaction → Confirm → Bill/Invoice → Payment → Journal Entry → Account
Balances → Reports**, end to end, with every number traceable back to an
actual posted journal entry — on top of real multi-month history, not a
single staged transaction.
