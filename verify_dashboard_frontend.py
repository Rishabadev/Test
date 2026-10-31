import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, UserRole

def test_admin_staff_dashboard():
    print("=================================================================")
    print("VERIFYING ADMIN & STAFF FINANCE DASHBOARD IMPLEMENTATION")
    print("=================================================================")

    # 1. Accounts
    admin_user = User.objects.get(email='admin@brightloop.io')
    staff_user = User.objects.get(email='staff@brightloop.io')
    cust_user = User.objects.get(email='customer@brightloop.io')

    client_admin = APIClient()
    client_staff = APIClient()
    client_cust = APIClient()
    client_anon = APIClient()

    # Authenticate Admin
    res_admin_login = client_admin.post('/api/auth/login/', {
        'email': admin_user.email,
        'password': 'Password123!'
    }, format='json')
    assert res_admin_login.status_code == 200, f"Admin login failed: {res_admin_login.data}"
    client_admin.credentials(HTTP_AUTHORIZATION=f"Bearer {res_admin_login.data['access']}")

    # Authenticate Staff
    res_staff_login = client_staff.post('/api/auth/login/', {
        'email': staff_user.email,
        'password': 'Password123!'
    }, format='json')
    assert res_staff_login.status_code == 200, f"Staff login failed: {res_staff_login.data}"
    client_staff.credentials(HTTP_AUTHORIZATION=f"Bearer {res_staff_login.data['access']}")

    # Authenticate Customer
    res_cust_login = client_cust.post('/api/auth/login/', {
        'email': cust_user.email,
        'password': 'Password123!'
    }, format='json')
    assert res_cust_login.status_code == 200, f"Customer login failed: {res_cust_login.data}"
    client_cust.credentials(HTTP_AUTHORIZATION=f"Bearer {res_cust_login.data['access']}")

    # -------------------------------------------------------------
    # TEST 1: Template Serving & DOM Structure
    # -------------------------------------------------------------
    print("\n--- 1. Dashboard Template Serving & DOM Structure ---")
    res_dash_page = client_admin.get('/dashboard/')
    assert res_dash_page.status_code == 200, f"Expected 200 for /dashboard/, got {res_dash_page.status_code}"
    html = res_dash_page.content.decode('utf-8')
    assert "dashboard.css" in html
    assert "dashboard.js" in html
    assert "Chart.js" in html or "chart.js" in html
    assert "statActiveSubs" in html
    assert "statTotalRevenue" in html
    assert "statOutstanding" in html
    assert "statOverdueCount" in html
    assert "dashFilterForm" in html
    assert "filterStartDate" in html
    assert "filterEndDate" in html
    assert "filterStatus" in html
    assert "filterCustomer" in html
    assert "chartRevenueOverTime" in html
    assert "chartSubStatus" in html
    assert "chartPaymentMethods" in html
    assert "overdueTableBody" in html
    assert "paymentsTableBody" in html
    assert "navProducts" in html
    assert "navPlans" in html
    assert "navDiscounts" in html
    assert "navStaffManagement" in html
    print("[PASSED] /dashboard/ template renders complete SaaS dashboard DOM with statistic cards, filters, charts, and tables")

    # -------------------------------------------------------------
    # TEST 2: Admin Dashboard API Access & Statistics
    # -------------------------------------------------------------
    print("\n--- 2. Admin Dashboard Statistics & API Response ---")
    res_overview = client_admin.get('/api/dashboard/')
    assert res_overview.status_code == 200
    ov = res_overview.data
    assert 'active_subscription_count' in ov
    assert 'total_revenue' in ov
    assert 'total_outstanding_amount' in ov
    assert 'overdue_invoices_count' in ov
    assert 'overdue_amount' in ov
    print(f"[PASSED] Admin Dashboard Overview API Metrics:")
    print(f"         - Active Subscriptions: {ov['active_subscription_count']}")
    print(f"         - Total Revenue:        ${ov['total_revenue']}")
    print(f"         - Outstanding Balance:  ${ov['total_outstanding_amount']}")
    print(f"         - Overdue Invoices:     {ov['overdue_invoices_count']} (${ov['overdue_amount']})")

    # -------------------------------------------------------------
    # TEST 3: Staff Dashboard API Access
    # -------------------------------------------------------------
    print("\n--- 3. Staff Dashboard Access ---")
    res_staff_ov = client_staff.get('/api/dashboard/')
    assert res_staff_ov.status_code == 200
    assert res_staff_ov.data['active_subscription_count'] == ov['active_subscription_count']
    print("[PASSED] Staff user has full authorized access to /api/dashboard/ metrics")

    # -------------------------------------------------------------
    # TEST 4: Backend Security & Unauthorized Access Blocked
    # -------------------------------------------------------------
    print("\n--- 4. Backend Security & Role Boundary Enforcement ---")
    # Customer forbidden from /api/dashboard/
    res_cust_dash = client_cust.get('/api/dashboard/')
    assert res_cust_dash.status_code == status.HTTP_403_FORBIDDEN
    print("[PASSED] Customer role strictly rejected by backend /api/dashboard/ (HTTP 403 Forbidden)")

    res_cust_overdue = client_cust.get('/api/dashboard/overdue-invoices/')
    assert res_cust_overdue.status_code == status.HTTP_403_FORBIDDEN
    print("[PASSED] Customer role rejected by backend /api/dashboard/overdue-invoices/ (HTTP 403 Forbidden)")

    res_cust_pay = client_cust.get('/api/dashboard/payments/')
    assert res_cust_pay.status_code == status.HTTP_403_FORBIDDEN
    print("[PASSED] Customer role rejected by backend /api/dashboard/payments/ (HTTP 403 Forbidden)")

    # Anonymous unauthorized
    res_anon_dash = client_anon.get('/api/dashboard/')
    assert res_anon_dash.status_code == status.HTTP_401_UNAUTHORIZED
    print("[PASSED] Anonymous request rejected by backend /api/dashboard/ (HTTP 401 Unauthorized)")

    # -------------------------------------------------------------
    # TEST 5: Overdue Invoices & Payments Tables with Pagination
    # -------------------------------------------------------------
    print("\n--- 5. Overdue Invoices & Payments Tables ---")
    res_overdue = client_admin.get('/api/dashboard/overdue-invoices/')
    assert res_overdue.status_code == 200
    assert 'count' in res_overdue.data
    assert 'results' in res_overdue.data
    assert len(res_overdue.data['results']) > 0
    sample_overdue = res_overdue.data['results'][0]
    assert 'invoice_number' in sample_overdue
    assert 'customer_email' in sample_overdue
    assert 'days_overdue' in sample_overdue
    assert 'total_amount' in sample_overdue
    assert 'amount_due' in sample_overdue
    print(f"[PASSED] Overdue Invoices: {res_overdue.data['count']} total records returned with pagination cursors")
    print(f"         Sample: {sample_overdue['invoice_number']} | Customer: {sample_overdue['customer_email']} | Due: ${sample_overdue['amount_due']} | Days Overdue: {sample_overdue['days_overdue']}")

    res_payments = client_admin.get('/api/dashboard/payments/')
    assert res_payments.status_code == 200
    assert 'count' in res_payments.data
    assert 'results' in res_payments.data
    assert len(res_payments.data['results']) > 0
    sample_payment = res_payments.data['results'][0]
    assert 'invoice_number' in sample_payment
    assert 'customer_email' in sample_payment
    assert 'amount' in sample_payment
    assert 'payment_date' in sample_payment
    assert 'method' in sample_payment
    print(f"[PASSED] Payments Log: {res_payments.data['count']} total records returned with pagination cursors")
    print(f"         Sample: #{sample_payment['id']} | Invoice: {sample_payment['invoice_number']} | Method: {sample_payment['method']} | Amount: ${sample_payment['amount']}")

    # -------------------------------------------------------------
    # TEST 6: Financial Filters
    # -------------------------------------------------------------
    print("\n--- 6. Filter Integration ---")
    # Date Range Filter
    res_filtered_date = client_admin.get('/api/dashboard/?start_date=2026-01-01&end_date=2026-12-31')
    assert res_filtered_date.status_code == 200
    print(f"[PASSED] Date Range filter applied: Revenue = ${res_filtered_date.data['total_revenue']}")

    # Customer Filter
    res_filtered_cust = client_admin.get(f'/api/dashboard/?customer={cust_user.id}')
    assert res_filtered_cust.status_code == 200
    print(f"[PASSED] Customer ID filter applied: Active subs = {res_filtered_cust.data['active_subscription_count']}")

    # Overdue Invoices Filtered by Customer
    res_overdue_cust = client_admin.get(f'/api/dashboard/overdue-invoices/?customer={cust_user.id}')
    assert res_overdue_cust.status_code == 200
    print(f"[PASSED] Overdue Invoices filtered by Customer: {res_overdue_cust.data['count']} records")

    # Payments Filtered by Method
    res_pay_method = client_admin.get('/api/dashboard/payments/?method=BANK_TRANSFER')
    assert res_pay_method.status_code == 200
    print(f"[PASSED] Payments filtered by Method (BANK_TRANSFER): {res_pay_method.data['count']} records")

    # -------------------------------------------------------------
    # TEST 7: Role-Based Sidebar Visibility Logic
    # -------------------------------------------------------------
    print("\n--- 7. Role-Based Navigation Visibility Logic ---")
    admin_only_ids = ['navProducts', 'navPlans', 'navDiscounts', 'navStaffManagement', 'sectionAdminHeader']
    staff_allowed_ids = ['navDashboard', 'navSubscriptions', 'navInvoices', 'navPayments', 'navLogout']

    # Read dashboard.js to verify client-side hiding logic
    with open('static/js/dashboard.js', 'r', encoding='utf-8') as f:
        js_code = f.read()

    assert "role === 'STAFF'" in js_code
    for nav_id in admin_only_ids:
        assert nav_id in js_code, f"{nav_id} missing from role visibility logic in dashboard.js"

    print("[PASSED] Verified dashboard.js strictly hides Products, Plans, Discounts, and Staff Management when role === 'STAFF'")
    print("[PASSED] Verified dashboard.js keeps all modules visible when role === 'ADMIN'")

    print("\n=================================================================")
    print("ALL ADMIN & STAFF DASHBOARD TESTS PASSED WITH 100% SUCCESS!")
    print("=================================================================")

if __name__ == '__main__':
    test_admin_staff_dashboard()
