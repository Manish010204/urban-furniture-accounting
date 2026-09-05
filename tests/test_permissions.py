"""Role-boundary coverage: Admin / Accountant / Contact, and unauthenticated
access, across every module — verifying the spec's permission table is
actually enforced, not just documented."""
from app.database import SessionLocal
from app.models import Contact, ContactType, User, UserRole
from app.security import hash_password
from tests.conftest import SEED_CREDENTIALS


def login(client, role="admin"):
    login_id, password = SEED_CREDENTIALS[role]
    r = client.post("/login", data={"login_id": login_id, "password": password}, follow_redirects=True)
    assert r.status_code == 200
    return r


def logout(client):
    client.get("/logout", follow_redirects=True)


def redirected_away_from(response, path: str) -> bool:
    return path not in response.url.path


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------

def test_unauthenticated_user_redirected_from_dashboard(client):
    logout(client)
    r = client.get("/", follow_redirects=True)
    assert "/login" in r.url.path


def test_unauthenticated_user_redirected_from_contacts(client):
    logout(client)
    r = client.get("/contacts", follow_redirects=True)
    assert "/login" in r.url.path


def test_unauthenticated_user_cannot_post_transactions(client):
    logout(client)
    r = client.post("/purchases/new", data={"vendor_id": "1", "date": "2026-01-01",
                                             "product_id": ["1"], "qty": ["1"], "unit_price": ["1"]},
                     follow_redirects=True)
    assert "/login" in r.url.path


# ---------------------------------------------------------------------------
# Accountant: can create/view, cannot edit/archive master data
# ---------------------------------------------------------------------------

def test_accountant_can_view_all_master_data_lists(client):
    login(client, "accountant")
    for page in ["/contacts", "/products", "/accounts", "/journals", "/analytic-accounts", "/budgets",
                 "/journal-entries", "/purchases", "/sales", "/payments", "/reports"]:
        r = client.get(page)
        assert r.status_code == 200, f"{page} returned {r.status_code} for accountant"


def test_accountant_cannot_edit_contact(client):
    login(client, "accountant")
    r = client.get("/contacts/1/edit", follow_redirects=True)
    assert redirected_away_from(r, "/contacts/1/edit")


def test_accountant_cannot_archive_contact(client):
    login(client, "accountant")
    r = client.post("/contacts/1/archive", follow_redirects=True)
    assert redirected_away_from(r, "/contacts/1/archive")
    # Azure Furniture (contact id 1) must remain untouched
    r2 = client.get("/contacts/1")
    assert "Archived" not in r2.text


def test_accountant_cannot_edit_product(client):
    login(client, "accountant")
    r = client.get("/products/1/edit", follow_redirects=True)
    assert redirected_away_from(r, "/products/1/edit")


def test_accountant_cannot_archive_product(client):
    login(client, "accountant")
    r = client.post("/products/1/archive", follow_redirects=True)
    assert redirected_away_from(r, "/products/1/archive")


def test_accountant_cannot_edit_account(client):
    login(client, "accountant")
    r = client.get("/accounts/1/edit", follow_redirects=True)
    assert redirected_away_from(r, "/accounts/1/edit")


def test_accountant_cannot_edit_journal(client):
    login(client, "accountant")
    r = client.get("/journals/1/edit", follow_redirects=True)
    assert redirected_away_from(r, "/journals/1/edit")


def test_accountant_can_create_purchase_order(client):
    login(client, "accountant")
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-16", "product_id": ["1"], "qty": ["1"], "unit_price": ["100"],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Purchase order created" in r.text


def test_accountant_can_create_sales_order(client):
    login(client, "accountant")
    r = client.post("/sales/new", data={
        "customer_id": "2", "date": "2026-01-16", "product_id": ["1"], "qty": ["1"], "unit_price": ["100"],
        "tax_percent": ["0"],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Sales order created" in r.text


# ---------------------------------------------------------------------------
# Contact role: fully blocked from every admin/accountant-only page
# ---------------------------------------------------------------------------

CONTACT_BLOCKED_PAGES = [
    "/contacts", "/products", "/accounts", "/journals", "/journal-entries",
    "/analytic-accounts", "/budgets", "/purchases", "/sales", "/payments",
    "/reports", "/reports/balance-sheet", "/reports/profit-loss", "/reports/budget",
]


def test_contact_role_blocked_from_every_admin_page(client):
    login(client, "contact")
    for page in CONTACT_BLOCKED_PAGES:
        r = client.get(page, follow_redirects=True)
        assert redirected_away_from(r, page), f"contact should not reach {page}"


def test_contact_role_sees_financial_portal_not_command_center(client):
    login(client, "contact")
    r = client.get("/")
    assert "My Financial Portal" in r.text
    assert "Business Pulse" not in r.text
    assert "Action Center" not in r.text


def test_contact_role_cannot_create_purchase_order(client):
    login(client, "contact")
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-16", "product_id": ["1"], "qty": ["1"], "unit_price": ["100"],
    }, follow_redirects=True)
    assert redirected_away_from(r, "/purchases/new")


# ---------------------------------------------------------------------------
# Contact data isolation: a contact user must never see another party's data
# ---------------------------------------------------------------------------

def _create_second_contact_user(login_id: str, contact_name: str, contact_type: ContactType) -> int:
    """Creates a Contact + a linked User directly against the app's real
    database (mirrors what app/seed.py does for Nimesh Pathak) so we can
    prove cross-customer data isolation over HTTP."""
    db = SessionLocal()
    try:
        contact = Contact(name=contact_name, type=contact_type)
        db.add(contact)
        db.flush()
        user = User(name=contact_name, login_id=login_id, email=f"{login_id}@isolation-test.com",
                    password_hash=hash_password("Isolation@123"), role=UserRole.contact, contact_id=contact.id)
        db.add(user)
        db.commit()
        return contact.id
    finally:
        db.close()


def test_contact_user_cannot_see_another_customers_invoice(client):
    login(client, "admin")
    # Isolated second customer with their own portal login
    other_contact_id = _create_second_contact_user("isotest1", "Isolation Test Customer", ContactType.customer)

    r = client.post("/sales/new", data={
        "customer_id": str(other_contact_id), "date": "2026-01-17",
        "product_id": ["1"], "qty": ["1"], "unit_price": ["1000"], "tax_percent": ["0"],
    }, follow_redirects=True)
    so_id = int(r.url.path.rstrip("/").split("/")[-1])
    client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    r = client.post(f"/sales/{so_id}/generate-invoice", data={"invoice_date": "2026-01-17", "due_date": "2026-02-01"},
                     follow_redirects=True)
    invoice_id = int(r.url.path.rstrip("/").split("/")[-1])

    # Nimesh Pathak (a different customer) must not be able to view or pay it
    login(client, "contact")
    r = client.get(f"/sales/invoices/{invoice_id}", follow_redirects=True)
    assert redirected_away_from(r, f"/sales/invoices/{invoice_id}")
    r = client.get(f"/sales/invoices/{invoice_id}/pay", follow_redirects=True)
    assert redirected_away_from(r, f"/sales/invoices/{invoice_id}/pay")

    r = client.get("/")
    assert f"INV" not in r.text or str(invoice_id) not in r.text
