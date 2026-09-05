"""Smoke tests: the application starts, connects to SQLite, and every major
page/workflow responds without error. Uses the real seeded demo application."""
from tests.conftest import SEED_CREDENTIALS


def login(client, role="admin"):
    login_id, password = SEED_CREDENTIALS[role]
    r = client.post("/login", data={"login_id": login_id, "password": password}, follow_redirects=True)
    assert r.status_code == 200
    return r


def test_app_starts_and_serves_login_page(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Urban Furniture" in r.text


def test_invalid_login_rejected(client):
    r = client.post("/login", data={"login_id": "admin1", "password": "wrong-password"})
    assert r.status_code == 400
    assert "Invalid Login Id or Password" in r.text


def test_signup_creates_accountant_and_can_log_in(client):
    r = client.post("/signup", data={
        "name": "New Accountant", "login_id": "newacct1", "email": "newacct@test.com",
        "password": "NewPass@123", "confirm_password": "NewPass@123",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Sign In" in r.text

    r = client.post("/login", data={"login_id": "newacct1", "password": "NewPass@123"}, follow_redirects=True)
    assert r.status_code == 200
    r = client.get("/contacts")
    assert r.status_code == 200  # accountant can view master data
    r = client.get("/contacts/1/edit")
    assert "/contacts/1/edit" not in r.url.path  # but not edit/archive (admin-only)


def test_signup_rejects_weak_password(client):
    r = client.post("/signup", data={
        "name": "Weak Pw", "login_id": "weakpw1", "email": "weakpw@test.com",
        "password": "weakpass", "confirm_password": "weakpass",
    })
    assert r.status_code == 400
    assert "Password" in r.text


def test_signup_rejects_duplicate_login_id(client):
    client.post("/signup", data={
        "name": "Dup One", "login_id": "dupuser1", "email": "dup1@test.com",
        "password": "Strong@123", "confirm_password": "Strong@123",
    })
    r = client.post("/signup", data={
        "name": "Dup Two", "login_id": "dupuser1", "email": "dup2@test.com",
        "password": "Strong@123", "confirm_password": "Strong@123",
    })
    assert r.status_code == 400
    assert "already taken" in r.text


def test_dashboard_loads_after_login(client):
    login(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text


def test_seed_data_present_on_dashboard_and_lists(client):
    login(client)
    r = client.get("/contacts")
    assert "Azure Furniture" in r.text
    assert "Nimesh Pathak" in r.text
    r = client.get("/products")
    assert "Office Chair" in r.text
    r = client.get("/accounts")
    assert "Cash" in r.text and "Bank" in r.text and "Debtors" in r.text


MAJOR_PAGES = [
    "/", "/contacts", "/products", "/accounts", "/journals", "/journal-entries",
    "/analytic-accounts", "/budgets", "/purchases", "/purchases/new", "/sales",
    "/sales/new", "/payments", "/reports", "/reports/balance-sheet",
    "/reports/profit-loss", "/reports/budget",
]


def test_all_major_pages_load(client):
    login(client)
    for page in MAJOR_PAGES:
        r = client.get(page)
        assert r.status_code == 200, f"{page} returned {r.status_code}"


def test_create_and_read_contact(client):
    login(client)
    r = client.post("/contacts/new", data={
        "name": "Smoke Test Vendor", "type": "vendor", "email": "smoke@test.com",
        "mobile": "9999999999", "city": "Delhi", "state": "Delhi", "pincode": "110001",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Smoke Test Vendor" in r.text
    r = client.get("/contacts")
    assert "Smoke Test Vendor" in r.text


def test_create_transaction_generate_bill_and_register_payment(client):
    login(client)
    # Vendor id 1 = Azure Furniture, product id 1 = Office Chair (from seed order)
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-10",
        "product_id": ["1"], "qty": ["2"], "unit_price": ["2800"],
    }, follow_redirects=True)
    assert r.status_code == 200
    po_id = int(r.url.path.rstrip("/").split("/")[-1])

    r = client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    assert r.status_code == 200

    r = client.post(f"/purchases/{po_id}/convert",
                     data={"invoice_date": "2026-01-11", "due_date": "2026-01-26"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Vendor Bill" in r.text
    bill_id = int(r.url.path.rstrip("/").split("/")[-1])

    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "5600", "method": "bank"},
                     follow_redirects=True)
    assert r.status_code == 200
    assert "Payment recorded" in r.text or "Paid" in r.text


def test_reports_render_with_data(client):
    login(client)
    for page in ["/reports/balance-sheet", "/reports/profit-loss", "/reports/budget"]:
        r = client.get(page)
        assert r.status_code == 200


def test_contact_profile_image_upload(client):
    import base64
    login(client)
    # 1x1 transparent PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    r = client.post(
        "/contacts/new",
        data={"name": "Avatar Test Contact", "type": "customer"},
        files={"profile_image": ("avatar.png", png_bytes, "image/png")},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "/static/uploads/contacts/" in r.text


def test_archived_vendor_rejected_in_new_purchase_order(client):
    login(client)
    r = client.post("/contacts/new", data={
        "name": "Archived Vendor Co", "type": "vendor",
    }, follow_redirects=True)
    vendor_id = int(r.url.path.rstrip("/").split("/")[-1])
    client.post(f"/contacts/{vendor_id}/archive", follow_redirects=True)

    r = client.post("/purchases/new", data={
        "vendor_id": str(vendor_id), "date": "2026-01-15",
        "product_id": ["1"], "qty": ["1"], "unit_price": ["100"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "active vendor" in r.text


def test_cannot_convert_unconfirmed_purchase_order(client):
    login(client)
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-25",
        "product_id": ["1"], "qty": ["1"], "unit_price": ["2800"],
    }, follow_redirects=True)
    po_id = int(r.url.path.rstrip("/").split("/")[-1])
    r = client.get(f"/purchases/{po_id}/convert", follow_redirects=True)
    assert "Confirm the order" in r.text


def test_budget_confirm_and_revise_lifecycle(client):
    import re
    login(client)
    client.post("/analytic-accounts/new", data={"name": "E2E Marketing", "type": "expense"},
                follow_redirects=True)

    r = client.get("/budgets/new")
    match = re.search(r'<option value="(\d+)">E2E Marketing', r.text)
    assert match
    analytic_id = int(match.group(1))

    r = client.post("/budgets/new", data={
        "name": "E2E Test Budget", "period_start": "2026-01-01", "period_end": "2026-12-31",
        "responsible_person": "Nimesh Pathak",
        "analytic_account_id": [str(analytic_id)], "committed_amount": ["10000"],
    }, follow_redirects=True)
    assert r.status_code == 200
    budget_id = int(r.url.path.rstrip("/").split("/")[-1])
    assert "Draft" in r.text

    r = client.post(f"/budgets/{budget_id}/confirm", follow_redirects=True)
    assert "Confirmed" in r.text

    r = client.get(f"/budgets/{budget_id}/revise")
    line_match = re.search(r'name="line_id" value="(\d+)"', r.text)
    assert line_match
    line_id = line_match.group(1)

    r = client.post(f"/budgets/{budget_id}/revise", data={
        "name": "E2E Test Budget Revised", "line_id": [line_id], "committed_amount": ["15000"],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Revision Of" in r.text

    r = client.get(f"/budgets/{budget_id}")
    assert "Revised" in r.text
    assert "Revised With" in r.text


def test_confirming_po_over_budget_shows_non_blocking_warning(client):
    import re
    login(client)
    client.post("/analytic-accounts/new", data={"name": "E2E Tight Budget Line", "type": "expense"},
                follow_redirects=True)
    r = client.get("/budgets/new")
    analytic_id = int(re.search(r'<option value="(\d+)">E2E Tight Budget Line', r.text).group(1))

    r = client.post("/budgets/new", data={
        "name": "E2E Tight Budget", "period_start": "2020-01-01", "period_end": "2030-12-31",
        "responsible_person": "Nimesh Pathak",
        "analytic_account_id": [str(analytic_id)], "committed_amount": ["100"],
    }, follow_redirects=True)
    budget_id = int(r.url.path.rstrip("/").split("/")[-1])
    client.post(f"/budgets/{budget_id}/confirm", follow_redirects=True)

    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-30",
        "product_id": ["1"], "qty": ["10"], "unit_price": ["2800"],
        "analytic_account_id": [str(analytic_id)],
    }, follow_redirects=True)
    po_id = int(r.url.path.rstrip("/").split("/")[-1])

    r = client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    assert r.status_code == 200
    assert "exceeds the remaining budget" in r.text
    # non-blocking: the order is still confirmed despite the warning
    assert "Confirmed" in r.text


def test_login_lockout_after_max_failed_attempts(client):
    client.post("/signup", data={
        "name": "Lockout Test", "login_id": "lockout1", "email": "lockout1@test.com",
        "password": "Correct@123", "confirm_password": "Correct@123",
    })
    for _ in range(5):
        r = client.post("/login", data={"login_id": "lockout1", "password": "WrongPass@1"})
        assert r.status_code == 400
    # 6th attempt, even with the CORRECT password, should now be blocked by the lockout
    r = client.post("/login", data={"login_id": "lockout1", "password": "Correct@123"})
    assert r.status_code == 400
    assert "Too many failed attempts" in r.text


def test_cross_origin_post_is_blocked(client):
    login(client)
    r = client.post(
        "/contacts/new",
        data={"name": "Should Not Be Created", "type": "vendor"},
        headers={"Origin": "http://evil.example.com"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "blocked" in r.headers["location"]
    r = client.get("/contacts")
    assert "Should Not Be Created" not in r.text


def test_404_page_renders(client):
    r = client.get("/this-page-does-not-exist")
    assert r.status_code == 404
    assert "Page not found" in r.text


def test_dashboard_shows_order_status_counts(client):
    login(client)
    r = client.get("/")
    assert "quickstatus" in r.text
    assert "Confirmed" in r.text and "Draft" in r.text


def test_contacts_and_products_kanban_view_renders(client):
    login(client)
    r = client.get("/contacts?view=kanban")
    assert r.status_code == 200
    assert "kanban-grid" in r.text
    r = client.get("/products?view=kanban")
    assert r.status_code == 200
    assert "kanban-grid" in r.text


def test_product_image_upload(client):
    import base64
    login(client)
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    r = client.post(
        "/products/new",
        data={"name": "Image Test Product", "type": "goods", "sales_price": "100", "cost_price": "50"},
        files={"image": ("chair.png", png_bytes, "image/png")},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "/static/uploads/products/" in r.text


def test_vendor_bill_overpayment_rejected(client):
    login(client)
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-20",
        "product_id": ["1"], "qty": ["1"], "unit_price": ["2800"],
    }, follow_redirects=True)
    po_id = int(r.url.path.rstrip("/").split("/")[-1])
    client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)

    r = client.post(f"/purchases/{po_id}/convert",
                     data={"invoice_date": "2026-01-21", "due_date": "2026-02-05"}, follow_redirects=True)
    bill_id = int(r.url.path.rstrip("/").split("/")[-1])

    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "999999", "method": "bank"},
                     follow_redirects=True)
    assert r.status_code == 400
    assert "cannot exceed" in r.text
