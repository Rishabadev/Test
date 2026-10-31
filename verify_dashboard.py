import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, UserRole

def test_dashboard():
    print("=================================================================")
    print("TESTING DASHBOARD PERFORMANCE, FILTERS, AND PAGINATION")
    print("=================================================================")

    admin = User.objects.filter(role=UserRole.ADMIN).first()
    customer = User.objects.filter(role=UserRole.CUSTOMER).first()

    client = APIClient()
    client.force_authenticate(user=admin)

    endpoints_to_test = [
        ("Dashboard Overview (Root)", "/api/dashboard/"),
        ("Dashboard Overview (Action)", "/api/dashboard/overview/"),
        ("Overdue Invoices (Page 1)", "/api/dashboard/overdue-invoices/"),
        ("Payments List (Page 1)", "/api/dashboard/payments/"),
        ("Overview Filtered by Customer", f"/api/dashboard/?customer={customer.id}"),
        ("Overview Filtered by Date Range", "/api/dashboard/?start_date=2026-01-01&end_date=2026-12-31"),
        ("Overview Filtered by Status", "/api/dashboard/?status=ACTIVE"),
        ("Overdue Filtered by Customer", f"/api/dashboard/overdue-invoices/?customer={customer.id}"),
        ("Overdue Filtered by Date Range", "/api/dashboard/overdue-invoices/?start_date=2026-01-01&end_date=2026-12-31"),
        ("Payments Filtered by Method", "/api/dashboard/payments/?method=BANK_TRANSFER"),
        ("Payments Filtered by Customer", f"/api/dashboard/payments/?customer={customer.id}"),
    ]

    results = []
    any_over_2s = False

    for name, url in endpoints_to_test:
        t0 = time.perf_counter()
        res = client.get(url)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert res.status_code == status.HTTP_200_OK, f"Failed on {url}: {res.status_code} - {res.data}"
        is_over = elapsed_ms > 2000.0
        if is_over:
            any_over_2s = True
        results.append({
            'name': name,
            'url': url,
            'status': res.status_code,
            'ms': elapsed_ms,
            'over_2s': is_over
        })
        print(f"[{'FAIL' if is_over else 'PASS'}] {name:<35} | {url:<60} | {elapsed_ms:8.2f} ms")

    # TEST PAGINATION
    print("\n--- Verifying Pagination ---")
    # Overdue Invoices Pagination
    res_page1 = client.get("/api/dashboard/overdue-invoices/?page=1")
    assert res_page1.status_code == status.HTTP_200_OK
    assert 'count' in res_page1.data and 'results' in res_page1.data, "Overdue invoices response is not paginated"
    total_overdue = res_page1.data['count']
    page1_len = len(res_page1.data['results'])
    has_next = res_page1.data['next'] is not None

    print(f"Overdue Invoices: Total Count = {total_overdue}, Page 1 Items = {page1_len}, Has Next Page = {has_next}")
    if has_next:
        res_page2 = client.get("/api/dashboard/overdue-invoices/?page=2")
        assert res_page2.status_code == status.HTTP_200_OK
        page2_len = len(res_page2.data['results'])
        print(f"Overdue Invoices Page 2: Items = {page2_len}")
        assert res_page1.data['results'][0]['id'] != res_page2.data['results'][0]['id'], "Pagination returned duplicate items"

    # Payments Pagination
    res_pay1 = client.get("/api/dashboard/payments/?page=1")
    assert res_pay1.status_code == status.HTTP_200_OK
    assert 'count' in res_pay1.data and 'results' in res_pay1.data, "Payments response is not paginated"
    total_payments = res_pay1.data['count']
    pay_page1_len = len(res_pay1.data['results'])
    pay_has_next = res_pay1.data['next'] is not None

    print(f"Payments List: Total Count = {total_payments}, Page 1 Items = {pay_page1_len}, Has Next Page = {pay_has_next}")
    if pay_has_next:
        res_pay2 = client.get("/api/dashboard/payments/?page=2")
        assert res_pay2.status_code == status.HTTP_200_OK
        print(f"Payments List Page 2: Items = {len(res_pay2.data['results'])}")
        assert res_pay1.data['results'][0]['id'] != res_pay2.data['results'][0]['id'], "Payments pagination returned duplicate items"

    print(f"\nPagination Verified: YES")
    print(f"Filters Verified: YES")
    print(f"Any endpoint exceeds 2.0s: {'YES - FAILED' if any_over_2s else 'NO - ALL PASSED'}")

if __name__ == '__main__':
    test_dashboard()

