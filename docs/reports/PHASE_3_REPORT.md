# Phase 3 Report

## Objective
Implement the minimal double-entry accounting engine: journal entries,
debit/credit validation, derived account balances, and the four core
posting rules.

## Accounting Rules Implemented (`app/services/accounting.py`)

| Transaction | Debit | Credit |
|---|---|---|
| Vendor Bill posted | Purchases Expense | Creditors |
| Vendor Payment (bank/cash) | Creditors | Bank or Cash |
| Customer Invoice posted | Debtors | Sales Income (+ Tax Payable if tax > 0) |
| Customer Payment (cash/bank) | Cash or Bank | Debtors |

`create_journal_entry()` is the single choke point every posting rule calls
through: it sums debit/credit across the given lines and raises
`UnbalancedEntryError` unless they are exactly equal (and > 0), before any
row is written. This makes it structurally impossible to post an unbalanced
entry — the manual Journal Entry UI (Phase 2) and every transaction flow
(Phases 4-5) all route through this same function.

`account_balance()` / `account_raw_balance()` derive a balance by summing
`JournalEntryLine.debit - credit` for that account across every posted
entry — never a stored running total, so it can't drift from what was
actually posted.

## Debit/Credit Examples
- Balanced: Debit Bank 100, Credit Capital 100 → accepted.
- Unbalanced: Debit Bank 100, Credit Capital 90 → `UnbalancedEntryError`
  raised, entry rolled back, nothing written.

## Data Flow
Transaction (bill/invoice/payment) → posting function builds a list of
`{account, debit, credit}` lines → `create_journal_entry()` validates and
persists `JournalEntry` + `JournalEntryLine` rows → `account_balance()` /
`services/reports.py` read those rows to compute balances and reports. There
is no separate "ledger" table — the journal entry lines *are* the ledger.

## Tests (`tests/test_domain.py`)
- `test_balanced_journal_entry_is_accepted`
- `test_unbalanced_journal_entry_is_rejected`
- `test_vendor_bill_posting_creates_expected_accounting_effect`
- `test_vendor_payment_posting_creates_expected_accounting_effect`
- `test_customer_invoice_posting_creates_expected_accounting_effect`
- `test_customer_payment_posting_creates_expected_accounting_effect`

Each posting test asserts both that the resulting entry is balanced (total
debit == total credit) and that the correct accounts moved by the correct
amounts.

## Test Results
24/24 passing (full suite, reported in Phase 8).

## Known Simplifications
- No sub-ledgers (e.g. no per-vendor "creditors" sub-account) — all vendors
  share the single Creditors account, all customers share Debtors. This
  matches the spec's minimal-engine instruction; per-party detail is instead
  visible on the Vendor Bill / Customer Invoice records themselves.
- No period close / retained-earnings transfer — the Balance Sheet instead
  folds current-period net profit into "Retained Earnings" live (see Phase 6).

## Git Commit
`e261d9f` (shared — see Phase 1 report).

## Next Phase
Phase 4 — Purchase Flow.
