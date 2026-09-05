import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import LOGIN_LOCKOUT_MINUTES, LOGIN_MAX_FAILED_ATTEMPTS
from app.database import get_db
from app.models import User, UserRole
from app.security import hash_password, verify_password
from app.templating import templates
from app.validators import ValidationError, validate_login_id, validate_password_strength

router = APIRouter()
logger = logging.getLogger("app.auth")


def _utcnow() -> datetime:
    """Naive UTC now, matching the naive DateTime columns used for locked_until."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {"request": request, "user": None})


@router.post("/login")
def login_submit(request: Request, login_id: str = Form(...), password: str = Form(...),
                  db: Session = Depends(get_db)):
    def render_error(message: str):
        return templates.TemplateResponse(request, "auth/login.html", {
            "request": request, "user": None, "error": message, "login_id": login_id,
        }, status_code=400)

    user = db.scalar(select(User).where(User.login_id == login_id.strip()))

    if user and user.locked_until and user.locked_until > _utcnow():
        minutes_left = max(1, int((user.locked_until - _utcnow()).total_seconds() // 60) + 1)
        logger.warning("Login blocked for locked account %s (%s minutes remaining)", login_id, minutes_left)
        return render_error(f"Too many failed attempts. Try again in {minutes_left} minute(s).")

    if not user or not verify_password(password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= LOGIN_MAX_FAILED_ATTEMPTS:
                user.locked_until = _utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
                logger.warning("Account %s locked for %s minutes after %s failed attempts",
                               login_id, LOGIN_LOCKOUT_MINUTES, user.failed_login_attempts)
            db.commit()
        logger.info("Failed login attempt for login_id=%s", login_id)
        return render_error("Invalid Login Id or Password")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    request.session["user_id"] = user.id
    logger.info("User %s (%s) logged in", user.login_id, user.role.value)
    return RedirectResponse(url="/", status_code=303)


@router.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse(request, "auth/signup.html", {"request": request, "user": None})


@router.post("/signup")
def signup_submit(
    request: Request,
    name: str = Form(...),
    login_id: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    def render_error(message: str):
        return templates.TemplateResponse(request, "auth/signup.html", {
            "request": request, "user": None, "error": message,
            "form": {"name": name, "login_id": login_id, "email": email},
        }, status_code=400)

    try:
        if not name.strip():
            raise ValidationError("Name is required.")
        validate_login_id(login_id)
        if db.scalar(select(User).where(User.login_id == login_id.strip())):
            raise ValidationError("This Login ID is already taken.")
        if not email.strip():
            raise ValidationError("Email is required.")
        if db.scalar(select(User).where(User.email == email.strip())):
            raise ValidationError("This email is already registered.")
        validate_password_strength(password)
        if password != confirm_password:
            raise ValidationError("Passwords do not match.")
    except ValidationError as e:
        return render_error(e.message)

    user = User(
        name=name.strip(), login_id=login_id.strip(), email=email.strip(),
        password_hash=hash_password(password), role=UserRole.accountant,
    )
    db.add(user)
    db.commit()
    return RedirectResponse(url="/login?success=Account+created.+Please+sign+in.", status_code=303)


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "auth/forgot_password.html", {"request": request, "user": None})


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
