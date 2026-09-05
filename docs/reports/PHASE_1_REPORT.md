# Phase 1 Report

## Objective
Stand up the FastAPI project foundation: app skeleton, SQLite database via
SQLAlchemy, base Jinja2 layout with navigation, session-based auth scaffold,
and the pytest setup.

## Note on phase boundaries
Phases 1-6 were implemented and committed together as one integrated
increment (commit `e261d9f`) because the modules are tightly interdependent —
the accounting engine (Phase 3) needs the Chart of Accounts model (Phase 2),
the dashboard (part of Phase 1's base layout) needs the reporting service
(Phase 6) to show summary cards, etc. Splitting them into artificially
independent, separately-runnable commits would have meant repeatedly
stubbing and un-stubbing code for no real benefit. Each phase report below
describes the slice of that same commit relevant to it; test results are
reported once, at the end, since the full suite only became meaningful once
every phase's code existed.

## Implementation
- `app/database.py`: SQLAlchemy engine/session factory, SQLite at
  `data/app.db` (overridable via `DATABASE_URL` env var for tests).
- `app/main.py`: FastAPI app, `SessionMiddleware` for cookie-session auth,
  static file mount, startup hook that creates tables and seeds demo data,
  a 403 handler that redirects home with an error message.
- `app/templating.py`: shared `Jinja2Templates` instance.
- `app/templates/base.html` + `_macros.html`: sidebar navigation (role-aware —
  admin/accountant see the full module list, contact users see only "My
  Invoices & Bills"), topbar with current user + role badge + "Switch User",
  flash message banners driven by `?success=`/`?error=` query params.
- `app/static/style.css`: the full design system (CSS variables, cards,
  tables, badges, forms, empty states) used by every later page.
- `app/auth.py` + `app/routers/auth.py` + `templates/auth/login.html`: demo
  login page listing every seeded `User` with a one-click "Sign in" button
  (no password) — satisfies the spec's "simple demo login / role switcher"
  requirement; `require_role(*roles)` FastAPI dependency guards every route.
- `app/routers/dashboard.py` + templates: `/` branches by role — admin/
  accountant get the full dashboard (Phase 7 polishes this further),
  contact users get their own invoices/bills list.

## Files Changed
See commit `e261d9f` — foundation files: `app/main.py`, `app/database.py`,
`app/templating.py`, `app/auth.py`, `app/routers/auth.py`,
`app/routers/dashboard.py`, `app/templates/base.html`, `_macros.html`,
`static/style.css`, `templates/auth/*`, `templates/dashboard/*`,
`requirements.txt`.

## Database Setup
SQLite file created via `Base.metadata.create_all()` on FastAPI startup —
no migration framework, per the prototype-scope instruction.

## Routes
`GET /login`, `POST /login/{user_id}`, `GET /logout`, `GET /`.

## Tests
`tests/conftest.py` sets `DATABASE_URL` to an isolated temp file before the
app is imported, and exposes a session-scoped `client` (FastAPI TestClient)
fixture plus an in-memory `db_session` fixture for unit-level tests.
`tests/test_smoke.py::test_app_starts_and_serves_login_page` and
`test_dashboard_loads_after_login` cover this phase directly.

## Test Results
Full-suite results reported once in `docs/reports/PHASE_8_REPORT.md`;
24/24 tests pass as of this commit (see Phase 6 report for the first full run).

## Git Commit
`e261d9f` (shared across Phases 1-6) — pushed to `origin/main`.

## Known Limitations
No password/identity verification — anyone can pick any demo user. This is
intentional per the spec's explicit "no OAuth/JWT" instruction.

## Next Phase
Phase 2 — Master Data.
