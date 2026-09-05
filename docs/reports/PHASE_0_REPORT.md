# Phase 0 Report

## Objective
Inspect the repository and specification, decide the architecture, and produce a
requirements traceability matrix and phase plan before writing any application code.

## Repository state (start)
- `git status`: empty repo, branch `main`, no commits.
- `git remote -v`: `origin` already pointed at
  `https://github.com/Manish010204/urban-furniture-accounting.git` (correct).
- No README, no source files, no mockup image present in the working tree — the
  "visual mockup/reference" mentioned in the task exists only as the textual UI/UX
  section of the spec, so that section is used as the design source of truth.
- Environment: Python 3.13.2 available at `C:\Program Files\Python313\python`.
  `fastapi`, `SQLAlchemy`, `Jinja2`, `uvicorn`, `starlette`, `python-dotenv`,
  `itsdangerous` already installed globally; `pytest`, `httpx`, `python-multipart`
  are missing and will be added via `requirements.txt` in Phase 1.

## Architecture selected
FastAPI + Jinja2 server-rendered templates + SQLAlchemy 2.0 + SQLite, cookie-session
auth with a demo role switcher (no OAuth/JWT), plain service modules for
tax/accounting/reports (no repository/interface layers). Full rationale and package
layout are in `docs/IMPLEMENTATION_PLAN.md`.

## Requirements discovered
Full traceability matrix (requirement → feature → planned implementation → planned
test) is in `docs/REQUIREMENTS.md`, covering: roles/auth, all 6 master-data modules
(Contact, Product, Chart of Accounts, Journals, Journal Entries, Analytic Accounts,
Budgets), all 5 transaction types (PO, Vendor Bill, SO, Customer Invoice, Payment),
tax calculation, the 4 core accounting postings, the 3 reports, demo data, validation
rules, and the smoke/domain test requirements.

## Important assumptions
- No mockup image exists in-repo; UI is built to the spec's textual description of a
  modern accounting dashboard (sidebar nav, summary cards, tables with status badges).
- One vendor bill per PO and one invoice per SO (matches the spec's linear diagrams).
- Account "current balance" is always derived from journal entry lines, never stored,
  to guarantee reports can never drift from postings.

## Scope deliberately excluded
OAuth/SSO/JWT, multi-currency/multi-company, inventory/stock valuation, credit notes,
recurring invoices, Alembic migrations (using `create_all` instead) — all per the
spec's explicit "keep it simple" instructions.

## Planned implementation
See `docs/IMPLEMENTATION_PLAN.md` phase-by-phase breakdown and package layout.

## Acceptance criteria
Matches the spec's "Definition of Done" list; tracked to completion via
`docs/FINAL_AUDIT.md` at the end of the project.

## Git Commit
`7babad6` — "Phase 0: requirements analysis and implementation plan" — pushed to
`origin/main`.

## Next Phase
Phase 1 — Project foundation (FastAPI skeleton, DB, base layout, nav, pytest setup).
