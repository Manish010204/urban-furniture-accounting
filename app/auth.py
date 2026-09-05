from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_login(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_role(*roles: str):
    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        user = get_current_user(request, db)
        if not user:
            raise HTTPException(status_code=303, headers={"Location": "/login"})
        if roles and user.role.value not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to access this page.")
        return user
    return dependency


ADMIN_AND_ACCOUNTANT = ("admin", "accountant")
ALL_ROLES = ("admin", "accountant", "contact")
