# Demo Script (5-10 minutes)

Goal: show the complete accounting workflow —
**Business Command Center → Master Data → Purchase → Confirm → Vendor Bill
→ Payment → Accounting**, then
**Master Data → Sale → Confirm → Customer Invoice → Payment → Accounting**,
then **Reports** — using data that's already populated so the app looks
alive from the first click.

Start the app fresh so the seed data is in place and the numbers below
match exactly:

```bash
rm -f data/app.db     # optional — only if you've run the demo before
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**.

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
- **Revenue vs Expenses** — a 6-month trend chart (plain inline SVG, no
  charting library).
- **Action Center** — dynamically generated from real data (overdue
  invoices/bills, bills due soon, budgets near their limit, orders still in
  draft). Right now it likely says "You're all caught up" — that's correct
  and expected on a clean seed.

## 2. Master Data (1 min)

- **Contacts**: already has Azure Furniture (vendor), Nimesh Pathak
  (customer), Rahul Sharma (vendor). Open Nimesh Pathak's detail page to
  show the 360° view (Total Sales/Paid/Outstanding/Overdue) plus city/
  state/pincode.
- **Products**: Office Chair, Wooden Table, Sofa, Dining Table, Wooden
  Chair — open Office Chair to show sales price ₹4,500, cost price ₹2,800,
  and the computed **Gross Margin** (₹1,700).
- **Chart of Accounts**: point out Cash, Bank, Debtors, Creditors, Sales
  Income, Purchases Expense, Tax Payable, Capital — each with a **live
  balance** (Bank already shows ₹150,000 from the seeded opening capital).

## 3. Purchase Flow — Azure Furniture (2 min)

1. **Purchase → Purchase Order → New Purchase Order.**
   - Vendor: **Azure Furniture**
   - Product: **Office Chair**, Quantity **10**, Unit Price **2800**
     (auto-filled from the product's cost price)
   - Budget Analytics: **Store Operations** (optional, but pick it so the
     Budget Report below shows a real actual/variance)
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
6. Open **Chart of Accounts** — Bank has dropped to **₹122,000**, Creditors
   is back to **₹0**.

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
5. Open **Chart of Accounts** — Cash now shows **₹23,625**, Debtors is back
   to **₹0**, Tax Payable shows **₹1,125**.
6. Back on the **Sales** page, show the status filter chips (All/Draft/
   Confirmed/Invoiced/... and Not Paid/Partially Paid/Paid/Overdue on the
   invoices table below).

## 5. Reports (2 min)

- **Reports → Balance Sheet**: Assets (Cash ₹23,625 + Bank ₹122,000 +
  Debtors ₹0 = **₹145,625**) exactly equal Liabilities + Capital
  (Creditors ₹0 + Tax Payable ₹1,125 + Capital ₹150,000 + Retained
  Earnings −₹5,500 = **₹145,625**). Click **View Transactions** next to any
  row to drill down into the journal entries behind that number.
- **Reports → Profit & Loss**: Sales Income ₹22,500, Purchases Expense
  ₹28,000, Net Profit **−₹5,500**, Profit Margin shown as a percentage —
  explain this single demo run bought more than it sold (10 chairs in, 5
  out), which is exactly what the numbers should show; in a longer-running
  dataset the margin recovers as more sales are recorded.
- **Reports → Budget Report**: because the PO/SO above were tagged with
  Store Operations / Retail Sales, the Q Retail Sales Budget shows
  **Actual ₹22,500** against its ₹50,000 plan with a visual progress bar
  (variance ₹27,500), and the Q Store Operations Budget shows **Actual
  ₹28,000** against its ₹20,000 plan (variance −₹8,000, i.e. over budget,
  progress bar turns red) — both computed from the analytic-tagged
  postings, not hardcoded.

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
actual posted journal entry.
