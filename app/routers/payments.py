from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Payment, User
from app.templating import templates

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("")
def list_payments(request: Request, user: User = Depends(require_role("admin", "accountant")),
                   db: Session = Depends(get_db)):
    payments = db.scalars(select(Payment).order_by(Payment.id.desc())).all()
    return templates.TemplateResponse(request, "payments/list.html", {
        "request": request, "user": user, "active": "payments", "payments": payments,
    })
