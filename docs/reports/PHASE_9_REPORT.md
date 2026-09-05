# Phase 9 Report

## Objective
Prepare the repository for a hackathon demonstration: a complete README, a
timed demo script, and one final full test run.

## Implementation
- **`README.md`**: project overview, features, architecture, setup/run/test
  instructions, demo credentials and role table, demo workflow summary,
  seed data list, known limitations, and project structure.
- **`docs/DEMO_SCRIPT.md`**: a timed (5-10 minute) walkthrough covering
  master data → purchase flow (Azure Furniture) → sales flow (Nimesh
  Pathak, with tax) → all three reports → a quick role-switching
  demonstration. Includes the exact expected numbers at each step (so
  whoever demos it can immediately tell if something's off), and instructs
  tagging the PO/SO with analytic accounts so the Budget Report shows a
  real, non-zero actual/variance during the demo (the Phase 8 walkthrough
  used untagged ad-hoc transactions, which is why that report showed
  actual ₹0 — this is now called out explicitly in the demo script rather
  than left as a surprise).

## Files Changed
`README.md` (new), `docs/DEMO_SCRIPT.md` (new).

## Test Results (final run before demo prep)
```
$ rm -f data/app.db && python -m pytest -q
........................                                            [100%]
24 passed, 83 warnings in 3.53s
```

## Git Commit
See this phase's commit (README + demo script).

## Next
Final Requirements Audit (`docs/FINAL_AUDIT.md`).
