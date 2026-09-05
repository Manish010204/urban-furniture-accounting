from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Account, AccountType, User
from app.services.accounting import account_balance
from app.templating import templates
from app.validators import ValidationError

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
def list_accounts(request: Request, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    accounts = db.scalars(select(Account).order_by(Account.type, Account.name)).all()
    balances = {a.id: account_balance(db, a) for a in accounts}
    return templates.TemplateResponse("accounts/list.html", {
        "request": request, "user": user, "active": "accounts",
        "accounts": accounts, "balances": balances,
    })


@router.get("/new")
def new_account_form(request: Request, user: User = Depends(require_role("admin", "accountant"))):
    return templates.TemplateResponse("accounts/form.html", {
        "request": request, "user": user, "active": "accounts", "account": None,
    })


@router.post("/new")
def create_account(request: Request, name: str = Form(...), type: str = Form(...), code: str = Form(""),
                    user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    try:
        if not name.strip():
            raise ValidationError("Account name is required.")
        account = Account(name=name.strip(), type=AccountType(type), code=code or None)
        db.add(account)
        db.commit()
    except ValidationError as e:
        return templates.TemplateResponse("accounts/form.html", {
            "request": request, "user": user, "active": "accounts", "account": None, "error": e.message,
        }, status_code=400)
    return RedirectResponse(url="/accounts?success=Account+created", status_code=303)


@router.get("/{account_id}/edit")
def edit_account_form(account_id: int, request: Request, user: User = Depends(require_role("admin")),
                       db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        return RedirectResponse(url="/accounts?error=Account+not+found", status_code=303)
    return templates.TemplateResponse("accounts/form.html", {
        "request": request, "user": user, "active": "accounts", "account": account,
    })


@router.post("/{account_id}/edit")
def update_account(account_id: int, request: Request, name: str = Form(...), type: str = Form(...),
                    code: str = Form(""), user: User = Depends(require_role("admin")),
                    db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        return RedirectResponse(url="/accounts?error=Account+not+found", status_code=303)
    try:
        if not name.strip():
            raise ValidationError("Account name is required.")
        account.name = name.strip()
        account.type = AccountType(type)
        account.code = code or None
        db.commit()
    except ValidationError as e:
        return templates.TemplateResponse("accounts/form.html", {
            "request": request, "user": user, "active": "accounts", "account": account, "error": e.message,
        }, status_code=400)
    return RedirectResponse(url="/accounts?success=Account+updated", status_code=303)
