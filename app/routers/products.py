import os

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Product, ProductType, User
from app.templating import templates
from app.validators import ValidationError

router = APIRouter(prefix="/products", tags=["products"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "products")


def _save_product_image(product: Product, image: UploadFile | None) -> None:
    if not image or not image.filename:
        return
    ext = os.path.splitext(image.filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise ValidationError("Product image must be a JPG, PNG, WEBP, or GIF file.")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{product.id}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(image.file.read())
    product.image_path = f"/static/uploads/products/{filename}"


@router.get("")
def list_products(request: Request, q: str = "", type: str = "", show_archived: bool = False, view: str = "list",
                   user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    stmt = select(Product)
    if not show_archived:
        stmt = stmt.where(Product.is_archived == False)  # noqa: E712
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if type:
        stmt = stmt.where(Product.type == ProductType(type))
    products = db.scalars(stmt.order_by(Product.name)).all()
    return templates.TemplateResponse(request, "products/list.html", {
        "request": request, "user": user, "active": "products",
        "products": products, "q": q, "type": type, "show_archived": show_archived, "view": view,
    })


@router.get("/new")
def new_product_form(request: Request, user: User = Depends(require_role("admin", "accountant"))):
    return templates.TemplateResponse(request, "products/form.html", {
        "request": request, "user": user, "active": "products", "product": None,
    })


@router.post("/new")
def create_product(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    sales_price: float = Form(...),
    cost_price: float = Form(...),
    category: str = Form(""),
    image: UploadFile | None = File(None),
    user: User = Depends(require_role("admin", "accountant")),
    db: Session = Depends(get_db),
):
    try:
        if not name.strip():
            raise ValidationError("Product name is required.")
        if sales_price < 0 or cost_price < 0:
            raise ValidationError("Prices cannot be negative.")
        product = Product(
            name=name.strip(), type=ProductType(type), sales_price=sales_price,
            cost_price=cost_price, category=category or None,
        )
        db.add(product)
        db.flush()
        _save_product_image(product, image)
        db.commit()
    except ValidationError as e:
        return templates.TemplateResponse(request, "products/form.html", {
            "request": request, "user": user, "active": "products", "product": None, "error": e.message,
        }, status_code=400)
    return RedirectResponse(url=f"/products/{product.id}?success=Product+created", status_code=303)


@router.get("/{product_id}")
def product_detail(product_id: int, request: Request,
                    user: User = Depends(require_role("admin", "accountant")), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        return RedirectResponse(url="/products?error=Product+not+found", status_code=303)
    return templates.TemplateResponse(request, "products/detail.html", {
        "request": request, "user": user, "active": "products", "product": product,
    })


@router.get("/{product_id}/edit")
def edit_product_form(product_id: int, request: Request,
                       user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        return RedirectResponse(url="/products?error=Product+not+found", status_code=303)
    return templates.TemplateResponse(request, "products/form.html", {
        "request": request, "user": user, "active": "products", "product": product,
    })


@router.post("/{product_id}/edit")
def update_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    sales_price: float = Form(...),
    cost_price: float = Form(...),
    category: str = Form(""),
    image: UploadFile | None = File(None),
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        return RedirectResponse(url="/products?error=Product+not+found", status_code=303)
    try:
        if not name.strip():
            raise ValidationError("Product name is required.")
        if sales_price < 0 or cost_price < 0:
            raise ValidationError("Prices cannot be negative.")
        product.name = name.strip()
        product.type = ProductType(type)
        product.sales_price = sales_price
        product.cost_price = cost_price
        product.category = category or None
        _save_product_image(product, image)
        db.commit()
    except ValidationError as e:
        return templates.TemplateResponse(request, "products/form.html", {
            "request": request, "user": user, "active": "products", "product": product, "error": e.message,
        }, status_code=400)
    return RedirectResponse(url=f"/products/{product.id}?success=Product+updated", status_code=303)


@router.post("/{product_id}/archive")
def archive_product(product_id: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product:
        product.is_archived = not product.is_archived
        db.commit()
    return RedirectResponse(url=f"/products/{product_id}?success=Product+updated", status_code=303)
