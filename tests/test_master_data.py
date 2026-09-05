"""Functional coverage for every master-data module's CRUD, validation, and
archive behavior — Contacts, Products, Chart of Accounts, Journals, Analytic
Accounts, Budgets. Uses the real seeded app via the HTTP layer."""
from tests.conftest import SEED_CREDENTIALS


def login(client, role="admin"):
    login_id, password = SEED_CREDENTIALS[role]
    r = client.post("/login", data={"login_id": login_id, "password": password}, follow_redirects=True)
    assert r.status_code == 200
    return r


def _id_from_redirect(response) -> int:
    return int(response.url.path.rstrip("/").split("/")[-1])


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def test_create_and_edit_contact(client):
    login(client)
    r = client.post("/contacts/new", data={
        "name": "MD Test Contact", "type": "customer", "email": "mdtest@test.com",
        "mobile": "9000000010", "city": "Delhi", "state": "Delhi", "country": "India", "pincode": "110001",
    }, follow_redirects=True)
    assert r.status_code == 200
    contact_id = _id_from_redirect(r)
    assert "MD Test Contact" in r.text

    r = client.post(f"/contacts/{contact_id}/edit", data={
        "name": "MD Test Contact Updated", "type": "customer", "email": "mdtest@test.com",
        "mobile": "9000000010", "city": "Mumbai", "state": "Maharashtra", "country": "India", "pincode": "400001",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "MD Test Contact Updated" in r.text
    assert "Mumbai" in r.text


def test_contact_invalid_email_rejected(client):
    login(client)
    r = client.post("/contacts/new", data={"name": "Bad Email Co", "type": "vendor", "email": "not-an-email"},
                     follow_redirects=True)
    assert r.status_code == 400
    assert "valid email" in r.text


def test_contact_invalid_pincode_rejected(client):
    login(client)
    r = client.post("/contacts/new", data={"name": "Bad Pincode Co", "type": "vendor", "pincode": "AB"},
                     follow_redirects=True)
    assert r.status_code == 400
    assert "Pincode" in r.text


def test_contact_missing_name_rejected(client):
    login(client)
    r = client.post("/contacts/new", data={"name": "   ", "type": "vendor"}, follow_redirects=True)
    assert r.status_code == 400
    assert "Name is required" in r.text


def test_contact_archive_and_unarchive(client):
    login(client)
    r = client.post("/contacts/new", data={"name": "Archive Toggle Co", "type": "vendor"}, follow_redirects=True)
    contact_id = _id_from_redirect(r)

    r = client.post(f"/contacts/{contact_id}/archive", follow_redirects=True)
    assert "Archived" in r.text

    r = client.post(f"/contacts/{contact_id}/archive", follow_redirects=True)
    assert "Active" in r.text


def test_contacts_search_filter_works(client):
    login(client)
    client.post("/contacts/new", data={"name": "Unique Searchable Name Zephyr", "type": "vendor"},
                follow_redirects=True)
    r = client.get("/contacts?q=Zephyr")
    assert "Unique Searchable Name Zephyr" in r.text
    r = client.get("/contacts?q=NoSuchContactXYZ123")
    assert "Unique Searchable Name Zephyr" not in r.text


def test_contacts_type_filter_works(client):
    login(client)
    r = client.get("/contacts?type=customer")
    assert r.status_code == 200
    assert "Nimesh Pathak" in r.text
    assert "Azure Furniture" not in r.text


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def test_create_and_edit_product(client):
    login(client)
    r = client.post("/products/new", data={
        "name": "MD Test Stool", "type": "goods", "sales_price": "500", "cost_price": "300", "category": "Seating",
    }, follow_redirects=True)
    assert r.status_code == 200
    product_id = _id_from_redirect(r)
    assert "MD Test Stool" in r.text

    r = client.post(f"/products/{product_id}/edit", data={
        "name": "MD Test Stool Deluxe", "type": "goods", "sales_price": "600", "cost_price": "300", "category": "Seating",
    }, follow_redirects=True)
    assert "MD Test Stool Deluxe" in r.text


def test_product_negative_sales_price_rejected(client):
    login(client)
    r = client.post("/products/new", data={"name": "Bad Price Product", "type": "goods",
                                            "sales_price": "-10", "cost_price": "5"}, follow_redirects=True)
    assert r.status_code == 400
    assert "cannot be negative" in r.text


def test_product_missing_name_rejected(client):
    login(client)
    r = client.post("/products/new", data={"name": "  ", "type": "goods", "sales_price": "10", "cost_price": "5"},
                     follow_redirects=True)
    assert r.status_code == 400
    assert "Product name is required" in r.text


def test_product_archive_and_unarchive(client):
    login(client)
    r = client.post("/products/new", data={"name": "Archive Toggle Product", "type": "goods",
                                            "sales_price": "10", "cost_price": "5"}, follow_redirects=True)
    product_id = _id_from_redirect(r)
    r = client.post(f"/products/{product_id}/archive", follow_redirects=True)
    assert "Archived" in r.text
    r = client.post(f"/products/{product_id}/archive", follow_redirects=True)
    assert "Active" in r.text


def test_products_search_filter_works(client):
    login(client)
    r = client.get("/products?q=Office")
    assert "Office Chair" in r.text
    assert "Sofa" not in r.text


def test_products_type_filter_works(client):
    login(client)
    r = client.get("/products?type=goods")
    assert "Office Chair" in r.text


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------

def test_create_and_edit_account(client):
    login(client)
    r = client.post("/accounts/new", data={"name": "MD Test Ledger", "type": "expense", "code": "9001"},
                     follow_redirects=True)
    assert r.status_code == 200
    assert "MD Test Ledger" in r.text

    r = client.get("/accounts")
    import re
    # locate the account row by name to get its edit link
    idx = r.text.find("MD Test Ledger")
    snippet = r.text[idx:idx + 400]
    edit_match = re.search(r'/accounts/(\d+)/edit', snippet)
    assert edit_match
    account_id = int(edit_match.group(1))

    r = client.post(f"/accounts/{account_id}/edit", data={"name": "MD Test Ledger Renamed", "type": "expense", "code": "9001"},
                     follow_redirects=True)
    assert "MD Test Ledger Renamed" in r.text


def test_account_missing_name_rejected(client):
    login(client)
    r = client.post("/accounts/new", data={"name": "  ", "type": "asset"}, follow_redirects=True)
    assert r.status_code == 400
    assert "Account name is required" in r.text


# ---------------------------------------------------------------------------
# Journals
# ---------------------------------------------------------------------------

def test_create_and_edit_journal(client):
    login(client)
    r = client.post("/journals/new", data={"name": "MD Test Journal", "type": "cash"}, follow_redirects=True)
    assert r.status_code == 200
    assert "MD Test Journal" in r.text

    import re
    idx = r.text.find("MD Test Journal")
    snippet = r.text[idx:idx + 400]
    edit_match = re.search(r'/journals/(\d+)/edit', snippet)
    assert edit_match
    journal_id = int(edit_match.group(1))

    r = client.post(f"/journals/{journal_id}/edit", data={"name": "MD Test Journal Renamed", "type": "bank"},
                     follow_redirects=True)
    assert "MD Test Journal Renamed" in r.text


def test_journal_missing_name_rejected(client):
    login(client)
    r = client.post("/journals/new", data={"name": "  ", "type": "cash"}, follow_redirects=True)
    assert r.status_code == 400
    assert "Journal name is required" in r.text


# ---------------------------------------------------------------------------
# Analytic Accounts
# ---------------------------------------------------------------------------

def test_create_analytic_account(client):
    login(client)
    r = client.post("/analytic-accounts/new", data={"name": "MD Test Analytic", "type": "income"},
                     follow_redirects=True)
    assert r.status_code == 200
    assert "MD Test Analytic" in r.text


def test_analytic_account_missing_name_rejected(client):
    login(client)
    r = client.post("/analytic-accounts/new", data={"name": "  ", "type": "income"}, follow_redirects=True)
    assert r.status_code == 400
    assert "Name is required" in r.text


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def _first_analytic_account_id(client):
    import re
    r = client.post("/analytic-accounts/new", data={"name": "MD Budget Test Line", "type": "expense"},
                     follow_redirects=True)
    r2 = client.get("/budgets/new")
    match = re.search(r'<option value="(\d+)">MD Budget Test Line', r2.text)
    assert match
    return int(match.group(1))


def test_budget_missing_name_rejected(client):
    login(client)
    analytic_id = _first_analytic_account_id(client)
    r = client.post("/budgets/new", data={
        "name": "  ", "period_start": "2026-01-01", "period_end": "2026-12-31",
        "responsible_person": "Nimesh Pathak", "analytic_account_id": [str(analytic_id)], "committed_amount": ["1000"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "Budget name is required" in r.text


def test_budget_end_date_before_start_rejected(client):
    login(client)
    analytic_id = _first_analytic_account_id(client)
    r = client.post("/budgets/new", data={
        "name": "MD Bad Date Budget", "period_start": "2026-12-31", "period_end": "2026-01-01",
        "responsible_person": "Nimesh Pathak", "analytic_account_id": [str(analytic_id)], "committed_amount": ["1000"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "after period start" in r.text


def test_budget_negative_committed_amount_rejected(client):
    login(client)
    analytic_id = _first_analytic_account_id(client)
    r = client.post("/budgets/new", data={
        "name": "MD Negative Budget", "period_start": "2026-01-01", "period_end": "2026-12-31",
        "responsible_person": "Nimesh Pathak", "analytic_account_id": [str(analytic_id)], "committed_amount": ["-500"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "cannot be negative" in r.text


# ---------------------------------------------------------------------------
# Archived master data cannot be selected in new transactions
# ---------------------------------------------------------------------------

def test_archived_product_rejected_in_new_purchase_order(client):
    login(client)
    r = client.post("/products/new", data={"name": "Archived PO Product", "type": "goods",
                                            "sales_price": "10", "cost_price": "5"}, follow_redirects=True)
    product_id = _id_from_redirect(r)
    client.post(f"/products/{product_id}/archive", follow_redirects=True)

    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-01-15", "product_id": [str(product_id)], "qty": ["1"], "unit_price": ["10"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "archived" in r.text


def test_archived_customer_rejected_in_new_sales_order(client):
    login(client)
    r = client.post("/contacts/new", data={"name": "Archived SO Customer", "type": "customer"}, follow_redirects=True)
    customer_id = _id_from_redirect(r)
    client.post(f"/contacts/{customer_id}/archive", follow_redirects=True)

    r = client.post("/sales/new", data={
        "customer_id": str(customer_id), "date": "2026-01-15",
        "product_id": ["1"], "qty": ["1"], "unit_price": ["100"], "tax_percent": ["0"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "active customer" in r.text


def test_archived_product_rejected_in_new_sales_order(client):
    login(client)
    r = client.post("/products/new", data={"name": "Archived SO Product", "type": "goods",
                                            "sales_price": "10", "cost_price": "5"}, follow_redirects=True)
    product_id = _id_from_redirect(r)
    client.post(f"/products/{product_id}/archive", follow_redirects=True)

    r = client.post("/sales/new", data={
        "customer_id": "2", "date": "2026-01-15",
        "product_id": [str(product_id)], "qty": ["1"], "unit_price": ["10"], "tax_percent": ["0"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "archived" in r.text
