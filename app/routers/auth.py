from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.templating import templates

router = APIRouter()


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    users = db.scalars(select(User)).all()
    return templates.TemplateResponse("auth/login.html", {"request": request, "user": None, "users": users})


@router.post("/login/{user_id}")
def login_as(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user:
        request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
