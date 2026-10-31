import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, UserRole, Subscription, Invoice, InvoiceStatus

def test_customer_portal():
    print("=================================================================")
    print("VERIFYING BRIGHTLOOP CUSTOMER PORTAL IMPLEMENTATION & SECURITY")
    print("=================================================================")

    # 1. Setup Clients
    customer = User.objects.filter(email='customer@brightloop.io').first()
    customer2 = User.objects.filter(email='customer1@demo.com').first()

    client_cust = APIClient()
    client_cust2 = APIClient()

    # Authenticate via API
    res_login = client_cust.post('/api/auth/login/', {
        'email': customer.email,
        'password': 'Password123!'
    }, format='json')
    assert res_login.status_code == 200, f"Customer login failed: {res_login.data}"
    tokens = res_login.data
    client_cust.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    res_login2 = client_cust2.post('/api/auth/login/', {
        'email': customer2.email,
        'password': 'Password123!'
    }, format='json')
    tokens2 = res_login2.data
    client_cust2.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens2['access']}")

    # -------------------------------------------------------------
    # TEST 1: Portal Page Template Serving
    # -------------------------------------------------------------
    print("\n--- 1. Portal Page Template Serving ---")
    res_page = client_cust.get('/portal/')
    assert res_page.status_code == 200, f"Expected 200 for /portal/, got {res_page.status_code}"
    html = res_page.content.decode('utf-8')
    assert "portal.css" in html, "portal.css missing from portal template"
    assert "portal.js" in html, "portal.js missing from portal template"
    assert "portalSidebar" in html, "Sidebar element missing"
    assert "panel-overview" in html, "Overview panel missing"
    assert "panel-subscriptions" in html, "Subscriptions panel missing"
    assert "panel-invoices" in html, "Invoices panel missing"
    assert "panel-profile" in html, "Profile panel missing"
    assert "subscriptionDetailModal" in html, "Subscription detail modal missing"
    assert "invoiceDetailModal" in html, "Invoice detail modal missing"
    assert "btnModalPrint" in html, "Print button missing"
    print("[PASSED] /portal/ successfully serves complete SaaS customer portal template with all required panels and modals")

    # -------------------------------------------------------------
    # TEST 2: Customer Subscriptions API & Data Structure
    # -------------------------------------------------------------
    print("\n--- 2. Subscriptions Display & Attributes ---")
    res_subs = client_cust.get('/api/subscriptions/')
    assert res_subs.status_code == 200
    subs_list = res_subs.data if isinstance(res_subs.data, list) else res_subs.data.get('results', [])
    assert len(subs_list) > 0, f"Expected customer {customer.email} to have subscriptions"

    # Verify all returned subscriptions belong to this customer
    for s in subs_list:
        assert s['customer'] == customer.id, f"Foreign subscription {s['id']} leaked to customer {customer.id}!"
        assert 'subscription_number' in s
        assert 'plan_name' in s
        assert 'start_date' in s
        assert 'status' in s
        assert 'plan_billing_period' in s
        assert 'total_amount' in s

    sample_sub = subs_list[0]
    print(f"[PASSED] Customer successfully retrieved {len(subs_list)} own subscriptions:")
    print(f"         Sample: {sample_sub['subscription_number']} | Plan: {sample_sub['plan_name']} | Frequency: {sample_sub['plan_billing_period']} | Total: ${sample_sub['total_amount']} | Status: {sample_sub['status']}")

    # -------------------------------------------------------------
    # TEST 3: Customer Invoices API & Data Structure
    # -------------------------------------------------------------
    print("\n--- 3. Invoices Display & Attributes ---")
    res_invs = client_cust.get('/api/invoices/')
    assert res_invs.status_code == 200
    invs_list = res_invs.data if isinstance(res_invs.data, list) else res_invs.data.get('results', [])
    assert len(invs_list) > 0, f"Expected customer {customer.email} to have invoices"

    for inv in invs_list:
        assert inv['customer'] == customer.id, f"Foreign invoice {inv['id']} leaked to customer {customer.id}!"
        assert 'invoice_number' in inv
        assert 'issue_date' in inv
        assert 'due_date' in inv
        assert 'total_amount' in inv
        assert 'amount_paid' in inv
        assert 'amount_due' in inv
        assert 'status' in inv

    sample_inv = invs_list[0]
    print(f"[PASSED] Customer successfully retrieved {len(invs_list)} own invoices:")
    print(f"         Sample: {sample_inv['invoice_number']} | Total: ${sample_inv['total_amount']} | Paid: ${sample_inv['amount_paid']} | Due: ${sample_inv['amount_due']} | Status: {sample_inv['status']}")

    # -------------------------------------------------------------
    # TEST 4: Invoice Details & PDF Stream
    # -------------------------------------------------------------
    print("\n--- 4. Invoice Details Modal & PDF Generation ---")
    res_inv_detail = client_cust.get(f"/api/invoices/{sample_inv['id']}/")
    assert res_inv_detail.status_code == 200
    inv_detail = res_inv_detail.data
    assert 'lines' in inv_detail
    assert 'payments' in inv_detail
    assert 'customer_name' in inv_detail
    assert 'subtotal' in inv_detail
    assert 'tax_amount' in inv_detail
    assert 'discount_amount' in inv_detail

    # Verify PDF stream endpoint
    res_pdf = client_cust.get(f"/api/invoices/{sample_inv['id']}/pdf/")
    assert res_pdf.status_code == 200
    assert res_pdf['Content-Type'] == 'application/pdf'
    assert res_pdf.content.startswith(b'%PDF')
    print(f"[PASSED] Full invoice details retrieved with {len(inv_detail['lines'])} lines and {len(inv_detail['payments'])} payments")
    print(f"[PASSED] Invoice PDF generation returned {len(res_pdf.content)} bytes of valid PDF stream (%PDF-1.4)")

    # -------------------------------------------------------------
    # TEST 5: Cross-Customer Tenant Isolation
    # -------------------------------------------------------------
    print("\n--- 5. Security & Cross-Customer Isolation ---")
    # Customer 2's subscription and invoice
    res_subs2 = client_cust2.get('/api/subscriptions/')
    subs2_list = res_subs2.data if isinstance(res_subs2.data, list) else res_subs2.data.get('results', [])
    c2_sub_id = subs2_list[0]['id']

    res_invs2 = client_cust2.get('/api/invoices/')
    invs2_list = res_invs2.data if isinstance(res_invs2.data, list) else res_invs2.data.get('results', [])
    c2_inv_id = invs2_list[0]['id']

    # Customer 1 attempts to access Customer 2's subscription
    res_hack_sub = client_cust.get(f"/api/subscriptions/{c2_sub_id}/")
    assert res_hack_sub.status_code == 404, f"Customer 1 was able to access Customer 2 subscription! Got {res_hack_sub.status_code}"
    print(f"[PASSED] Cross-customer subscription access blocked (HTTP 404 Not Found)")

    # Customer 1 attempts to access Customer 2's invoice
    res_hack_inv = client_cust.get(f"/api/invoices/{c2_inv_id}/")
    assert res_hack_inv.status_code == 404, f"Customer 1 was able to access Customer 2 invoice! Got {res_hack_inv.status_code}"
    print(f"[PASSED] Cross-customer invoice access blocked (HTTP 404 Not Found)")

    # Customer 1 attempts to download Customer 2's invoice PDF
    res_hack_pdf = client_cust.get(f"/api/invoices/{c2_inv_id}/pdf/")
    assert res_hack_pdf.status_code in [404, 403], f"Customer 1 was able to download Customer 2 invoice PDF! Got {res_hack_pdf.status_code}"
    print(f"[PASSED] Cross-customer invoice PDF download blocked (HTTP {res_hack_pdf.status_code})")

    # Unauthenticated access to /api/subscriptions/ and /api/invoices/
    anon = APIClient()
    res_anon_subs = anon.get('/api/subscriptions/')
    res_anon_invs = anon.get('/api/invoices/')
    assert res_anon_subs.status_code == 401
    assert res_anon_invs.status_code == 401
    print("[PASSED] Unauthenticated API requests rejected with HTTP 401 Unauthorized")

    print("\n=================================================================")
    print("ALL CUSTOMER PORTAL TESTS PASSED WITH 100% SUCCESS!")
    print("=================================================================")

if __name__ == '__main__':
    test_customer_portal()
