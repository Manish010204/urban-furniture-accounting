from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Account, Journal, JournalType, User
from app.templating import templates
from app.validators import ValidationError

router = APIRouter(prefix="/journals", tags=["journals"])


@router.get("")
def list_journals(request: Request, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    journals = db.scalars(select(Journal).order_by(Journal.name)).all()
    return templates.TemplateResponse("journals/list.html", {
        "request": request, "user": user, "active": "journals", "journals": journals,
    })


@router.get("/new")
def new_journal_form(request: Request, user: User = Depends(require_role("admin", "accountant")),
                      db: Session = Depends(get_db)):
    accounts = db.scalars(select(Account).order_by(Account.name)).all()
    return templates.TemplateResponse("journals/form.html", {
        "request": request, "user": user, "active": "journals", "journal": None, "accounts": accounts,
    })


@router.post("/new")
def create_journal(request: Request, name: str = Form(...), type: str = Form(...),
                    default_debit_account_id: int = Form(None), default_credit_account_id: int = Form(None),
                    user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    if not name.strip():
        accounts = db.scalars(select(Account).order_by(Account.name)).all()
        return templates.TemplateResponse("journals/form.html", {
            "request": request, "user": user, "active": "journals", "journal": None, "accounts": accounts,
            "error": "Journal name is required.",
        }, status_code=400)
    journal = Journal(name=name.strip(), type=JournalType(type),
                       default_debit_account_id=default_debit_account_id or None,
                       default_credit_account_id=default_credit_account_id or None)
    db.add(journal)
    db.commit()
    return RedirectResponse(url="/journals?success=Journal+created", status_code=303)


@router.get("/{journal_id}/edit")
def edit_journal_form(journal_id: int, request: Request, user: User = Depends(require_role("admin")),
                       db: Session = Depends(get_db)):
    journal = db.get(Journal, journal_id)
    accounts = db.scalars(select(Account).order_by(Account.name)).all()
    if not journal:
        return RedirectResponse(url="/journals?error=Journal+not+found", status_code=303)
    return templates.TemplateResponse("journals/form.html", {
        "request": request, "user": user, "active": "journals", "journal": journal, "accounts": accounts,
    })


@router.post("/{journal_id}/edit")
def update_journal(journal_id: int, request: Request, name: str = Form(...), type: str = Form(...),
                    default_debit_account_id: int = Form(None), default_credit_account_id: int = Form(None),
                    user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    journal = db.get(Journal, journal_id)
    if not journal:
        return RedirectResponse(url="/journals?error=Journal+not+found", status_code=303)
    journal.name = name.strip() or journal.name
    journal.type = JournalType(type)
    journal.default_debit_account_id = default_debit_account_id or None
    journal.default_credit_account_id = default_credit_account_id or None
    db.commit()
    return RedirectResponse(url="/journals?success=Journal+updated", status_code=303)
