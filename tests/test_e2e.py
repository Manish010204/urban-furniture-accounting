"""End-to-end tests for the two critical workflows described in the spec:
Purchase Order -> Confirm -> Vendor Bill -> Payment -> Journal Entry, and
Sales Order -> Confirm -> Customer Invoice -> Payment -> Journal Entry.

Runs entirely through the HTTP layer (FastAPI TestClient) against the real
seeded application, exactly as a user would click through the demo.
"""
import re

from tests.conftest import SEED_CREDENTIALS


def login(client, role="admin"):
    login_id, password = SEED_CREDENTIALS[role]
    client.post("/login", data={"login_id": login_id, "password": password}, follow_redirects=True)


def _id_from_redirect(response) -> int:
    """The id of the record a POST redirected to, e.g. /purchases/7?success=... -> 7."""
    return int(response.url.path.rstrip("/").split("/")[-1])


def _extract_ids(html: str, pattern: str) -> list[int]:
    return [int(m) for m in re.findall(pattern, html)]


def test_end_to_end_purchase_flow(client):
    login(client)

    # Create a fresh vendor + product dedicated to this test so it never
    # collides with ids used by other tests sharing the same app instance.
    r = client.post("/contacts/new", data={
        "name": "E2E Vendor Co", "type": "vendor", "email": "e2e.vendor@test.com",
        "mobile": "9000000001", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001",
    }, follow_redirects=True)
    vendor_id = _id_from_redirect(r)

    r = client.post("/products/new", data={
        "name": "E2E Test Stool", "type": "goods", "sales_price": "1000", "cost_price": "600",
        "category": "Seating",
    }, follow_redirects=True)
    product_id = _id_from_redirect(r)

    # --- Step 1: Create Purchase Order --------------------------------
    r = client.post("/purchases/new", data={
        "vendor_id": str(vendor_id), "date": "2026-02-01",
        "product_id": [str(product_id)], "qty": ["4"], "unit_price": ["600"],
    }, follow_redirects=True)
    assert r.status_code == 200
    po_id = _id_from_redirect(r)
    assert "Draft" in r.text

    # --- Step 2: Confirm, then Convert to Vendor Bill ------------------
    r = client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    assert r.status_code == 200
    assert "Confirmed" in r.text

    r = client.post(f"/purchases/{po_id}/convert",
                     data={"invoice_date": "2026-02-02", "due_date": "2026-02-17"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Not Paid" in r.text
    bill_id = _id_from_redirect(r)

    r = client.get(f"/purchases/bills/{bill_id}")
    assert "₹2400.00" in r.text.replace(",", "")  # 4 * 600

    # --- Step 3: Register vendor payment through Bank ------------------
    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "2400", "method": "bank"},
                     follow_redirects=True)
    assert r.status_code == 200

    r = client.get(f"/purchases/bills/{bill_id}")
    assert "Paid" in r.text

    # --- Verify: journal entry balanced & posted ------------------------
    je_match = re.search(r"/journal-entries/(\d+)", r.text)
    assert je_match, "vendor bill should link to its journal entry"
    je_id = je_match.group(1)
    r = client.get(f"/journal-entries/{je_id}")
    assert "Balanced" in r.text


def test_end_to_end_sales_flow(client):
    login(client)

    r = client.post("/contacts/new", data={
        "name": "E2E Customer Co", "type": "customer", "email": "e2e.customer@test.com",
        "mobile": "9000000002", "city": "Bengaluru", "state": "Karnataka", "pincode": "560001",
    }, follow_redirects=True)
    customer_id = _id_from_redirect(r)

    r = client.post("/products/new", data={
        "name": "E2E Test Bench", "type": "goods", "sales_price": "2000", "cost_price": "1200",
        "category": "Seating",
    }, follow_redirects=True)
    product_id = _id_from_redirect(r)

    # --- Step 5: Create Sales Order (qty 5, with tax) -------------------
    r = client.post("/sales/new", data={
        "customer_id": str(customer_id), "date": "2026-02-05",
        "product_id": [str(product_id)], "qty": ["5"], "unit_price": ["2000"], "tax_percent": ["5"],
    }, follow_redirects=True)
    assert r.status_code == 200
    so_id = _id_from_redirect(r)

    r = client.get(f"/sales/{so_id}")
    assert "₹10000.00" in r.text.replace(",", "")   # subtotal 5*2000
    assert "₹500.00" in r.text.replace(",", "")     # tax 5%
    assert "₹10500.00" in r.text.replace(",", "")   # grand total

    # Cannot generate an invoice before the order is confirmed
    r = client.get(f"/sales/{so_id}/generate-invoice", follow_redirects=True)
    assert "Confirm the order" in r.text

    # --- Step 6: Confirm, then Generate Customer Invoice ----------------
    r = client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    assert r.status_code == 200
    assert "Confirmed" in r.text

    r = client.post(f"/sales/{so_id}/generate-invoice",
                     data={"invoice_date": "2026-02-05", "due_date": "2026-02-20"}, follow_redirects=True)
    assert r.status_code == 200
    invoice_id = _id_from_redirect(r)

    # Duplicate invoice generation must be rejected
    r = client.get(f"/sales/{so_id}/generate-invoice", follow_redirects=True)
    assert "already exists" in r.text

    # --- Step 7: Register customer payment through Cash -----------------
    r = client.post(f"/sales/invoices/{invoice_id}/pay", data={"amount": "10500", "method": "cash"},
                     follow_redirects=True)
    assert r.status_code == 200
    r = client.get(f"/sales/invoices/{invoice_id}")
    assert "Paid" in r.text

    # Overpayment / paying an already-paid invoice must be rejected
    r = client.post(f"/sales/invoices/{invoice_id}/pay", data={"amount": "1", "method": "cash"},
                     follow_redirects=True)
    assert "already fully paid" in r.text

    je_match = re.search(r"/journal-entries/(\d+)", client.get(f"/sales/invoices/{invoice_id}").text)
    assert je_match

    # --- Step 8: Reports reflect the transaction -------------------------
    r = client.get("/reports/profit-loss")
    assert "Sales Income" in r.text
    r = client.get("/reports/balance-sheet")
    assert "Debtors" in r.text
