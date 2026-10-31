import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, UserRole, Subscription, Invoice, Product, Plan, TaxRule, Discount

def test_roles():
    print("=================================================================")
    print("VERIFYING ROLE PERMISSIONS & CUSTOMER TENANCY ISOLATION")
    print("=================================================================")

    admin = User.objects.filter(role=UserRole.ADMIN).first()
    staff = User.objects.filter(role=UserRole.STAFF).first()
    customers = list(User.objects.filter(role=UserRole.CUSTOMER)[:2])
    customer1, customer2 = customers[0], customers[1]

    client_admin = APIClient()
    client_admin.force_authenticate(user=admin)

    client_staff = APIClient()
    client_staff.force_authenticate(user=staff)

    client_c1 = APIClient()
    client_c1.force_authenticate(user=customer1)

    client_c2 = APIClient()
    client_c2.force_authenticate(user=customer2)

    unauthenticated_client = APIClient()

    # 1. CATALOG PERMISSIONS
    print("\n--- 1. Catalog Permissions ---")
    # Staff cannot create product
    res = client_staff.post('/api/products/', {'name': 'Staff Prod', 'sales_price': '10.00'})
    assert res.status_code == status.HTTP_403_FORBIDDEN, f"Staff should not be able to create products, got {res.status_code}"
    print("[PASSED] Staff cannot create products (403 Forbidden)")

    # Customer cannot create product
    res = client_c1.post('/api/products/', {'name': 'Cust Prod', 'sales_price': '10.00'})
    assert res.status_code == status.HTTP_403_FORBIDDEN, f"Customer should not be able to create products, got {res.status_code}"
    print("[PASSED] Customer cannot create products (403 Forbidden)")

    # Admin can create product
    res = client_admin.post('/api/products/', {'name': 'Admin Prod', 'sales_price': '10.00'})
    assert res.status_code == status.HTTP_201_CREATED, f"Admin failed to create product: {res.status_code} - {res.data}"
    prod_id = res.data['id']
    print("[PASSED] Admin can create products (201 Created)")

    # Staff can read product
    res = client_staff.get(f'/api/products/{prod_id}/')
    assert res.status_code == status.HTTP_200_OK
    print("[PASSED] Staff can read products (200 OK)")

    # Clean up test product
    client_admin.delete(f'/api/products/{prod_id}/')

    # 2. DASHBOARD ACCESS
    print("\n--- 2. Dashboard Access ---")
    # Admin can access
    res = client_admin.get('/api/dashboard/')
    assert res.status_code == status.HTTP_200_OK
    print("[PASSED] Admin can access /api/dashboard/ (200 OK)")

    # Staff can access
    res = client_staff.get('/api/dashboard/')
    assert res.status_code == status.HTTP_200_OK
    print("[PASSED] Staff can access /api/dashboard/ (200 OK)")

    # Customer CANNOT access dashboard
    res = client_c1.get('/api/dashboard/')
    assert res.status_code == status.HTTP_403_FORBIDDEN
    print("[PASSED] Customer cannot access /api/dashboard/ (403 Forbidden)")

    # 3. PAYMENT CREATION
    print("\n--- 3. Payments Permissions ---")
    # Customer cannot post payment
    res = client_c1.post('/api/payments/', {'amount': '10.00'})
    assert res.status_code == status.HTTP_403_FORBIDDEN
    print("[PASSED] Customer cannot access /api/payments/ (403 Forbidden)")

    # 4. CUSTOMER TENANCY ISOLATION: SUBSCRIPTIONS
    print("\n--- 4. Customer Tenancy Isolation: Subscriptions ---")
    # Find or create a subscription belonging to customer1
    sub1 = Subscription.objects.filter(customer=customer1).first()
    sub2 = Subscription.objects.filter(customer=customer2).first()

    # Customer 1 listing subscriptions
    res_c1_list = client_c1.get('/api/subscriptions/')
    assert res_c1_list.status_code == status.HTTP_200_OK
    c1_sub_ids = [s['id'] for s in (res_c1_list.data['results'] if isinstance(res_c1_list.data, dict) else res_c1_list.data)]
    assert sub2.id not in c1_sub_ids, "Customer 1 can see Customer 2's subscription in list!"
    print(f"[PASSED] Customer 1 subscription list contains only their own subscriptions (Customer 2 sub excluded)")

    # Customer 1 retrieving Customer 1's subscription -> OK
    res_c1_own = client_c1.get(f'/api/subscriptions/{sub1.id}/')
    assert res_c1_own.status_code == status.HTTP_200_OK
    print(f"[PASSED] Customer 1 can retrieve own subscription {sub1.id} (200 OK)")

    # Customer 1 attempting to retrieve Customer 2's subscription -> 404 Not Found (isolated)
    res_c1_other = client_c1.get(f'/api/subscriptions/{sub2.id}/')
    assert res_c1_other.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN], f"Customer 1 should not access Customer 2 subscription, got {res_c1_other.status_code}"
    print(f"[PASSED] Customer 1 blocked from accessing Customer 2's subscription ({res_c1_other.status_code})")

    # 5. CUSTOMER TENANCY ISOLATION: INVOICES
    print("\n--- 5. Customer Tenancy Isolation: Invoices ---")
    inv1 = Invoice.objects.filter(customer=customer1).first()
    inv2 = Invoice.objects.filter(customer=customer2).first()

    # Customer 1 listing invoices
    res_c1_inv_list = client_c1.get('/api/invoices/')
    assert res_c1_inv_list.status_code == status.HTTP_200_OK
    c1_inv_ids = [inv['id'] for inv in (res_c1_inv_list.data['results'] if isinstance(res_c1_inv_list.data, dict) else res_c1_inv_list.data)]
    assert inv2.id not in c1_inv_ids, "Customer 1 can see Customer 2's invoice in list!"
    print(f"[PASSED] Customer 1 invoice list contains only their own invoices (Customer 2 invoice excluded)")

    # Customer 1 retrieving own invoice -> OK
    res_c1_inv_own = client_c1.get(f'/api/invoices/{inv1.id}/')
    assert res_c1_inv_own.status_code == status.HTTP_200_OK
    print(f"[PASSED] Customer 1 can retrieve own invoice {inv1.id} (200 OK)")

    # Customer 1 retrieving Customer 2's invoice -> 404 Not Found
    res_c1_inv_other = client_c1.get(f'/api/invoices/{inv2.id}/')
    assert res_c1_inv_other.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN], f"Customer 1 should not access Customer 2 invoice, got {res_c1_inv_other.status_code}"
    print(f"[PASSED] Customer 1 blocked from accessing Customer 2's invoice ({res_c1_inv_other.status_code})")

    # Customer 1 downloading Customer 2's PDF -> 404 / 403
    res_c1_pdf_other = client_c1.get(f'/api/invoices/{inv2.id}/pdf/')
    assert res_c1_pdf_other.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
    print(f"[PASSED] Customer 1 blocked from downloading Customer 2's invoice PDF ({res_c1_pdf_other.status_code})")

    print("\n=================================================================")
    print("ALL ROLE PERMISSIONS & TENANCY TESTS PASSED!")
    print("=================================================================")

if __name__ == '__main__':
    test_roles()
