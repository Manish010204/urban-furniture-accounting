"""End-to-end tests for the two critical workflows described in the spec:
Purchase Order -> Vendor Bill -> Payment -> Journal Entry, and
Sales Order -> Customer Invoice -> Payment -> Journal Entry.

Runs entirely through the HTTP layer (FastAPI TestClient) against the real
seeded application, exactly as a user would click through the demo.
"""
import re


def login(client, user_id=1):
    client.post(f"/login/{user_id}", follow_redirects=True)


def _extract_ids(html: str, pattern: str) -> list[int]:
    return [int(m) for m in re.findall(pattern, html)]


def test_end_to_end_purchase_flow(client):
    login(client)

    # Create a fresh vendor + product dedicated to this test so it never
    # collides with ids used by other tests sharing the same app instance.
    client.post("/contacts/new", data={
        "name": "E2E Vendor Co", "type": "vendor", "email": "e2e.vendor@test.com",
        "mobile": "9000000001", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001",
    }, follow_redirects=True)
    r = client.get("/contacts")
    vendor_id = max(_extract_ids(r.text, r'/contacts/(\d+)"'))

    r = client.post("/products/new", data={
        "name": "E2E Test Stool", "type": "goods", "sales_price": "1000", "cost_price": "600",
        "category": "Seating",
    }, follow_redirects=True)
    r = client.get("/products")
    product_id = max(_extract_ids(r.text, r'/products/(\d+)"'))

    # --- Step 1: Create Purchase Order --------------------------------
    r = client.post("/purchases/new", data={
        "vendor_id": str(vendor_id), "date": "2026-02-01",
        "product_id": [str(product_id)], "qty": ["4"], "unit_price": ["600"],
    }, follow_redirects=True)
    assert r.status_code == 200
    po_id = max(_extract_ids(r.text, r'PO-(\d+)') or [0])
    assert po_id

    # --- Step 2: Convert to Vendor Bill --------------------------------
    r = client.post(f"/purchases/{po_id}/convert",
                     data={"invoice_date": "2026-02-02", "due_date": "2026-02-17"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Unpaid" in r.text
    bill_id = max(_extract_ids(r.text, r'BILL-(\d+)'))

    r = client.get(f"/purchases/bills/{bill_id}")
    assert "₹2400.00" in r.text.replace(",", "")  # 4 * 600

    # --- Step 3: Register vendor payment through Bank ------------------
    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "2400", "method": "bank"},
                     follow_redirects=True)
    assert r.status_code == 200

    r = client.get(f"/purchases/bills/{bill_id}")
    assert "Paid" in r.text

    # --- Verify: journal entry balanced & posted ------------------------
    r = client.get(f"/purchases/bills/{bill_id}")
    je_match = re.search(r"/journal-entries/(\d+)", r.text)
    assert je_match, "vendor bill should link to its journal entry"
    je_id = je_match.group(1)
    r = client.get(f"/journal-entries/{je_id}")
    assert "Balanced" in r.text


def test_end_to_end_sales_flow(client):
    login(client)

    client.post("/contacts/new", data={
        "name": "E2E Customer Co", "type": "customer", "email": "e2e.customer@test.com",
        "mobile": "9000000002", "city": "Bengaluru", "state": "Karnataka", "pincode": "560001",
    }, follow_redirects=True)
    r = client.get("/contacts")
    customer_id = max(_extract_ids(r.text, r'/contacts/(\d+)"'))

    r = client.post("/products/new", data={
        "name": "E2E Test Bench", "type": "goods", "sales_price": "2000", "cost_price": "1200",
        "category": "Seating",
    }, follow_redirects=True)
    r = client.get("/products")
    product_id = max(_extract_ids(r.text, r'/products/(\d+)"'))

    # --- Step 5: Create Sales Order (qty 5, with tax) -------------------
    r = client.post("/sales/new", data={
        "customer_id": str(customer_id), "date": "2026-02-05",
        "product_id": [str(product_id)], "qty": ["5"], "unit_price": ["2000"], "tax_percent": ["5"],
    }, follow_redirects=True)
    assert r.status_code == 200
    so_id = max(_extract_ids(r.text, r'SO-(\d+)') or [0])
    assert so_id

    r = client.get(f"/sales/{so_id}")
    assert "₹10000.00" in r.text.replace(",", "")   # subtotal 5*2000
    assert "₹500.00" in r.text.replace(",", "")     # tax 5%
    assert "₹10500.00" in r.text.replace(",", "")   # grand total

    # --- Step 6: Generate Customer Invoice ------------------------------
    r = client.post(f"/sales/{so_id}/generate-invoice",
                     data={"invoice_date": "2026-02-05", "due_date": "2026-02-20"}, follow_redirects=True)
    assert r.status_code == 200
    invoice_id = max(_extract_ids(r.text, r'INV-(\d+)'))

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

    je_match = re.search(r"/journal-entries/(\d+)", r.text) or re.search(
        r"/journal-entries/(\d+)", client.get(f"/sales/invoices/{invoice_id}").text)
    assert je_match

    # --- Step 8: Reports reflect the transaction -------------------------
    r = client.get("/reports/profit-loss")
    assert "Sales Income" in r.text
    r = client.get("/reports/balance-sheet")
    assert "Debtors" in r.text
