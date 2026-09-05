"""Edge cases across the Purchase and Sales workflows not already covered by
test_e2e.py's happy-path walkthrough: double state-transitions, partial
payments, zero/negative amounts, empty-line rejection, and report filters."""
from tests.conftest import SEED_CREDENTIALS


def login(client, role="admin"):
    login_id, password = SEED_CREDENTIALS[role]
    r = client.post("/login", data={"login_id": login_id, "password": password}, follow_redirects=True)
    assert r.status_code == 200
    return r


def _id_from_redirect(response) -> int:
    return int(response.url.path.rstrip("/").split("/")[-1])


def _new_po(client, qty="1", unit_price="1000"):
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-02-10", "product_id": ["1"], "qty": [qty], "unit_price": [unit_price],
    }, follow_redirects=True)
    return _id_from_redirect(r)


def _new_so(client, qty="1", unit_price="1000", tax="0"):
    r = client.post("/sales/new", data={
        "customer_id": "2", "date": "2026-02-10", "product_id": ["1"], "qty": [qty],
        "unit_price": [unit_price], "tax_percent": [tax],
    }, follow_redirects=True)
    return _id_from_redirect(r)


# ---------------------------------------------------------------------------
# Purchase Order state machine
# ---------------------------------------------------------------------------

def test_po_cannot_be_confirmed_twice(client):
    login(client)
    po_id = _new_po(client)
    client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    r = client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    assert "Only draft orders can be confirmed" in r.text


def test_po_cannot_be_cancelled_after_billed(client):
    login(client)
    po_id = _new_po(client)
    client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    client.post(f"/purchases/{po_id}/convert", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                follow_redirects=True)
    r = client.post(f"/purchases/{po_id}/cancel", follow_redirects=True)
    assert "cannot be cancelled" in r.text


def test_po_can_be_cancelled_while_draft(client):
    login(client)
    po_id = _new_po(client)
    r = client.post(f"/purchases/{po_id}/cancel", follow_redirects=True)
    assert "Cancelled" in r.text


def test_purchase_order_requires_at_least_one_line(client):
    login(client)
    r = client.post("/purchases/new", data={"vendor_id": "1", "date": "2026-02-10"}, follow_redirects=True)
    assert r.status_code == 400
    assert "Add at least one product line" in r.text


def test_purchase_order_zero_quantity_rejected(client):
    login(client)
    r = client.post("/purchases/new", data={
        "vendor_id": "1", "date": "2026-02-10", "product_id": ["1"], "qty": ["0"], "unit_price": ["100"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "Quantity must be greater than zero" in r.text


def test_cannot_convert_po_twice(client):
    login(client)
    po_id = _new_po(client)
    client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    client.post(f"/purchases/{po_id}/convert", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                follow_redirects=True)
    r = client.get(f"/purchases/{po_id}/convert", follow_redirects=True)
    assert "already has a vendor bill" in r.text


# ---------------------------------------------------------------------------
# Vendor Bill payments
# ---------------------------------------------------------------------------

def test_vendor_bill_partial_payment_leaves_status_partially_paid(client):
    login(client)
    po_id = _new_po(client, qty="2", unit_price="1000")  # total 2000
    client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    r = client.post(f"/purchases/{po_id}/convert", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                     follow_redirects=True)
    bill_id = _id_from_redirect(r)

    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "500", "method": "bank"},
                     follow_redirects=True)
    assert "Partially Paid" in r.text

    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "1500", "method": "bank"},
                     follow_redirects=True)
    assert "Paid" in r.text


def test_vendor_payment_zero_amount_rejected(client):
    login(client)
    po_id = _new_po(client)
    client.post(f"/purchases/{po_id}/confirm", follow_redirects=True)
    r = client.post(f"/purchases/{po_id}/convert", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                     follow_redirects=True)
    bill_id = _id_from_redirect(r)

    r = client.post(f"/purchases/bills/{bill_id}/pay", data={"amount": "0", "method": "bank"},
                     follow_redirects=True)
    assert r.status_code == 400
    assert "greater than zero" in r.text


# ---------------------------------------------------------------------------
# Sales Order state machine
# ---------------------------------------------------------------------------

def test_so_cannot_be_confirmed_twice(client):
    login(client)
    so_id = _new_so(client)
    client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    r = client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    assert "Only draft orders can be confirmed" in r.text


def test_so_cannot_be_cancelled_after_invoiced(client):
    login(client)
    so_id = _new_so(client)
    client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    client.post(f"/sales/{so_id}/generate-invoice", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                follow_redirects=True)
    r = client.post(f"/sales/{so_id}/cancel", follow_redirects=True)
    assert "cannot be cancelled" in r.text


def test_so_can_be_cancelled_while_draft(client):
    login(client)
    so_id = _new_so(client)
    r = client.post(f"/sales/{so_id}/cancel", follow_redirects=True)
    assert "Cancelled" in r.text


def test_sales_order_requires_at_least_one_line(client):
    login(client)
    r = client.post("/sales/new", data={"customer_id": "2", "date": "2026-02-10"}, follow_redirects=True)
    assert r.status_code == 400
    assert "Add at least one product line" in r.text


def test_sales_order_negative_tax_rejected(client):
    login(client)
    r = client.post("/sales/new", data={
        "customer_id": "2", "date": "2026-02-10", "product_id": ["1"], "qty": ["1"],
        "unit_price": ["100"], "tax_percent": ["-5"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "Tax percent cannot be negative" in r.text


# ---------------------------------------------------------------------------
# Customer Invoice payments
# ---------------------------------------------------------------------------

def test_customer_invoice_partial_payment_leaves_status_partially_paid(client):
    login(client)
    so_id = _new_so(client, qty="2", unit_price="1000")  # total 2000
    client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    r = client.post(f"/sales/{so_id}/generate-invoice", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                     follow_redirects=True)
    invoice_id = _id_from_redirect(r)

    r = client.post(f"/sales/invoices/{invoice_id}/pay", data={"amount": "500", "method": "cash"},
                     follow_redirects=True)
    assert "Partially Paid" in r.text

    r = client.post(f"/sales/invoices/{invoice_id}/pay", data={"amount": "1500", "method": "cash"},
                     follow_redirects=True)
    assert "Paid" in r.text


def test_customer_payment_zero_amount_rejected(client):
    login(client)
    so_id = _new_so(client)
    client.post(f"/sales/{so_id}/confirm", follow_redirects=True)
    r = client.post(f"/sales/{so_id}/generate-invoice", data={"invoice_date": "2026-02-11", "due_date": "2026-02-26"},
                     follow_redirects=True)
    invoice_id = _id_from_redirect(r)

    r = client.post(f"/sales/invoices/{invoice_id}/pay", data={"amount": "0", "method": "cash"},
                     follow_redirects=True)
    assert r.status_code == 400
    assert "greater than zero" in r.text


# ---------------------------------------------------------------------------
# Manual Journal Entries
# ---------------------------------------------------------------------------

def test_manual_journal_entry_requires_two_lines(client):
    login(client)
    r = client.get("/accounts")
    import re
    account_ids = re.findall(r'/accounts/(\d+)/edit', r.text)
    assert account_ids
    r = client.post("/journal-entries/new", data={
        "journal_id": "1", "date": "2026-02-10", "reference": "Single line test",
        "account_id": [account_ids[0]], "debit": ["100"], "credit": ["0"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "at least two lines" in r.text


def test_manual_journal_entry_unbalanced_rejected(client):
    login(client)
    r = client.get("/accounts")
    import re
    account_ids = re.findall(r'/accounts/(\d+)/edit', r.text)
    assert len(account_ids) >= 2
    r = client.post("/journal-entries/new", data={
        "journal_id": "1", "date": "2026-02-10", "reference": "Unbalanced test",
        "account_id": [account_ids[0], account_ids[1]], "debit": ["100", "0"], "credit": ["0", "90"],
    }, follow_redirects=True)
    assert r.status_code == 400
    assert "not balanced" in r.text


def test_manual_journal_entry_balanced_posts_successfully(client):
    login(client)
    r = client.get("/accounts")
    import re
    account_ids = re.findall(r'/accounts/(\d+)/edit', r.text)
    assert len(account_ids) >= 2
    r = client.post("/journal-entries/new", data={
        "journal_id": "1", "date": "2026-02-10", "reference": "Balanced adjustment",
        "account_id": [account_ids[0], account_ids[1]], "debit": ["250", "0"], "credit": ["0", "250"],
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Journal entry posted" in r.text


# ---------------------------------------------------------------------------
# Report filters render correctly
# ---------------------------------------------------------------------------

def test_balance_sheet_as_of_date_filter(client):
    login(client)
    r = client.get("/reports/balance-sheet?as_of=2020-01-01")
    assert r.status_code == 200
    assert "Total Assets" in r.text


def test_profit_loss_since_and_as_of_filters(client):
    login(client)
    r = client.get("/reports/profit-loss?since=2026-01-01&as_of=2026-12-31")
    assert r.status_code == 200
    assert "Net Profit" in r.text
