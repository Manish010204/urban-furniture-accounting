"""Smoke tests: the application starts, connects to SQLite, and every major
page/workflow responds without error. Uses the real seeded demo application."""


def login(client, user_id=1):
    r = client.post(f"/login/{user_id}", follow_redirects=True)
    assert r.status_code == 200
    return r


def test_app_starts_and_serves_login_page(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Urban Furniture" in r.text


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
    assert "PO-" in r.text

    po_id = r.url.path.split("/")[-1] if "purchases/" in str(r.url) else None
    # fall back: fetch the purchases list and take the newest PO id
    r_list = client.get("/purchases")
    assert r_list.status_code == 200

    r = client.get("/purchases")
    # locate the highest PO id referenced on the page
    import re
    ids = [int(m) for m in re.findall(r"/purchases/(\d+)\"", r.text)]
    assert ids, "expected at least one purchase order id on the list page"
    new_po_id = max(ids)

    r = client.post(f"/purchases/{new_po_id}/convert",
                     data={"invoice_date": "2026-01-11", "due_date": "2026-01-26"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Vendor Bill" in r.text

    bill_ids = [int(m) for m in re.findall(r"/purchases/bills/(\d+)\"", r.text)]
    bill_id = max(bill_ids) if bill_ids else None
    if bill_id is None:
        r_list_bills = client.get("/purchases")
        bill_ids = [int(m) for m in re.findall(r"/purchases/bills/(\d+)\"", r_list_bills.text)]
        bill_id = max(bill_ids)

    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "5600", "method": "bank"},
                     follow_redirects=True)
    assert r.status_code == 200
    assert "Payment recorded" in r.text or "Paid" in r.text


def test_reports_render_with_data(client):
    login(client)
    for page in ["/reports/balance-sheet", "/reports/profit-loss", "/reports/budget"]:
        r = client.get(page)
        assert r.status_code == 200
