from datetime import date
from itertools import zip_longest

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Account, Contact, Journal, JournalEntry, JournalEntryLine, User
from app.services.accounting import UnbalancedEntryError, create_journal_entry
from app.templating import templates

router = APIRouter(prefix="/journal-entries", tags=["journal_entries"])


@router.get("")
def list_entries(request: Request, account: int = None,
                  user: User = Depends(require_role("admin", "accountant")),
                  db: Session = Depends(get_db)):
    query = select(JournalEntry)
    account_filter = None
    if account:
        account_filter = db.get(Account, account)
        query = query.join(JournalEntryLine, JournalEntryLine.entry_id == JournalEntry.id) \
                      .where(JournalEntryLine.account_id == account).distinct()
    entries = db.scalars(query.order_by(JournalEntry.id.desc())).all()
    return templates.TemplateResponse(request, "journal_entries/list.html", {
        "request": request, "user": user, "active": "journal_entries", "entries": entries,
        "account_filter": account_filter,
    })


@router.get("/new")
def new_entry_form(request: Request, user: User = Depends(require_role("admin", "accountant")),
                    db: Session = Depends(get_db)):
    journals = db.scalars(select(Journal).order_by(Journal.name)).all()
    accounts = db.scalars(select(Account).order_by(Account.name)).all()
    contacts = db.scalars(select(Contact).where(Contact.is_archived == False).order_by(Contact.name)).all()  # noqa: E712
    return templates.TemplateResponse(request, "journal_entries/form.html", {
        "request": request, "user": user, "active": "journal_entries",
        "journals": journals, "accounts": accounts, "contacts": contacts, "today": date.today().isoformat(),
    })


@router.post("/new")
async def create_entry(request: Request, user: User = Depends(require_role("admin", "accountant")),
                        db: Session = Depends(get_db)):
    form = await request.form()
    journal_id = int(form["journal_id"])
    entry_date = date.fromisoformat(form["date"])
    reference = form.get("reference", "")
    account_ids = form.getlist("account_id")
    partner_ids = form.getlist("partner_contact_id")
    debits = form.getlist("debit")
    credits = form.getlist("credit")

    lines = []
    for acc_id, partner_id, debit, credit in zip_longest(account_ids, partner_ids, debits, credits, fillvalue=""):
        if not acc_id:
            continue
        account = db.get(Account, int(acc_id))
        lines.append({
            "account": account, "debit": float(debit or 0), "credit": float(credit or 0),
            "partner_contact_id": int(partner_id) if partner_id else None,
        })

    journal = db.get(Journal, journal_id)
    journals = db.scalars(select(Journal).order_by(Journal.name)).all()
    accounts = db.scalars(select(Account).order_by(Account.name)).all()
    contacts = db.scalars(select(Contact).where(Contact.is_archived == False).order_by(Contact.name)).all()  # noqa: E712

    try:
        if len(lines) < 2:
            raise UnbalancedEntryError("A journal entry needs at least two lines.")
        create_journal_entry(db, journal, entry_date, reference, lines, source_type="manual")
        db.commit()
    except UnbalancedEntryError as e:
        db.rollback()
        return templates.TemplateResponse(request, "journal_entries/form.html", {
            "request": request, "user": user, "active": "journal_entries",
            "journals": journals, "accounts": accounts, "contacts": contacts,
            "today": entry_date.isoformat(), "error": str(e),
        }, status_code=400)
    return RedirectResponse(url="/journal-entries?success=Journal+entry+posted", status_code=303)


@router.get("/{entry_id}")
def entry_detail(entry_id: int, request: Request, user: User = Depends(require_role("admin", "accountant")),
                  db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        return RedirectResponse(url="/journal-entries?error=Entry+not+found", status_code=303)
    return templates.TemplateResponse(request, "journal_entries/detail.html", {
        "request": request, "user": user, "active": "journal_entries", "entry": entry,
    })
