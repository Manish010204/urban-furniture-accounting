import os

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Contact, ContactType, User
from app.templating import templates
from app.validators import ValidationError, validate_email, validate_pincode

router = APIRouter(prefix="/contacts", tags=["contacts"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "contacts")


def _save_profile_image(contact: Contact, profile_image: UploadFile | None) -> None:
    if not profile_image or not profile_image.filename:
        return
    ext = os.path.splitext(profile_image.filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise ValidationError("Profile image must be a JPG, PNG, WEBP, or GIF file.")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{contact.id}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(profile_image.file.read())
    contact.profile_image_path = f"/static/uploads/contacts/{filename}"


@router.get("")
def list_contacts(request: Request, q: str = "", type: str = "", show_archived: bool = False, view: str = "list",
                   user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    stmt = select(Contact)
    if not show_archived:
        stmt = stmt.where(Contact.is_archived == False)  # noqa: E712
    if q:
        stmt = stmt.where(Contact.name.ilike(f"%{q}%"))
    if type:
        stmt = stmt.where(Contact.type == ContactType(type))
    contacts = db.scalars(stmt.order_by(Contact.name)).all()
    return templates.TemplateResponse(request, "contacts/list.html", {
        "request": request, "user": user, "active": "contacts",
        "contacts": contacts, "q": q, "type": type, "show_archived": show_archived, "view": view,
    })


@router.get("/new")
def new_contact_form(request: Request, user: User = Depends(require_role("admin", "accountant"))):
    return templates.TemplateResponse(request, "contacts/form.html", {
        "request": request, "user": user, "active": "contacts", "contact": None,
    })


@router.post("/new")
def create_contact(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    email: str = Form(""),
    mobile: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form(""),
    pincode: str = Form(""),
    profile_image: UploadFile | None = File(None),
    user: User = Depends(require_role("admin", "accountant")),
    db: Session = Depends(get_db),
):
    try:
        if not name.strip():
            raise ValidationError("Name is required.")
        validate_email(email)
        validate_pincode(pincode)
        contact = Contact(
            name=name.strip(), type=ContactType(type), email=email or None, mobile=mobile or None,
            city=city or None, state=state or None, country=country or None, pincode=pincode or None,
        )
        db.add(contact)
        db.flush()
        _save_profile_image(contact, profile_image)
        db.commit()
    except ValidationError as e:
        return templates.TemplateResponse(request, "contacts/form.html", {
            "request": request, "user": user, "active": "contacts", "contact": None, "error": e.message,
            "form": {"name": name, "type": type, "email": email, "mobile": mobile, "city": city,
                     "state": state, "pincode": pincode},
        }, status_code=400)
    return RedirectResponse(url=f"/contacts/{contact.id}?success=Contact+created", status_code=303)


@router.get("/{contact_id}")
def contact_detail(contact_id: int, request: Request,
                    user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(url="/contacts?error=Contact+not+found", status_code=303)
    return templates.TemplateResponse(request, "contacts/detail.html", {
        "request": request, "user": user, "active": "contacts", "contact": contact,
    })


@router.get("/{contact_id}/edit")
def edit_contact_form(contact_id: int, request: Request,
                       user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(url="/contacts?error=Contact+not+found", status_code=303)
    return templates.TemplateResponse(request, "contacts/form.html", {
        "request": request, "user": user, "active": "contacts", "contact": contact,
    })


@router.post("/{contact_id}/edit")
def update_contact(
    contact_id: int,
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    email: str = Form(""),
    mobile: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    country: str = Form(""),
    pincode: str = Form(""),
    profile_image: UploadFile | None = File(None),
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    contact = db.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(url="/contacts?error=Contact+not+found", status_code=303)
    try:
        if not name.strip():
            raise ValidationError("Name is required.")
        validate_email(email)
        validate_pincode(pincode)
        contact.name = name.strip()
        contact.type = ContactType(type)
        contact.email = email or None
        contact.mobile = mobile or None
        contact.city = city or None
        contact.state = state or None
        contact.country = country or None
        contact.pincode = pincode or None
        _save_profile_image(contact, profile_image)
        db.commit()
    except ValidationError as e:
        return templates.TemplateResponse(request, "contacts/form.html", {
            "request": request, "user": user, "active": "contacts", "contact": contact, "error": e.message,
        }, status_code=400)
    return RedirectResponse(url=f"/contacts/{contact.id}?success=Contact+updated", status_code=303)


@router.post("/{contact_id}/archive")
def archive_contact(contact_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if contact:
        contact.is_archived = not contact.is_archived
        db.commit()
    return RedirectResponse(url=f"/contacts/{contact_id}?success=Contact+updated", status_code=303)
