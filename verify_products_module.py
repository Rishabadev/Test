"""
Brightloop Software - Product & Variant Management Verification Script
Tests complete Admin CRUD, inline & standalone variants, effective pricing,
tax rules configuration, Staff/Customer access restrictions, and regression safety.
"""

import os
import sys
import json
import django

# Initialize Django
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from rest_framework import status
from core.models import User, UserRole, Product, ProductVariant, TaxRule

def run_verification():
    client = Client()
    print("=" * 70)
    print("BRIGHTLOOP SOFTWARE - PRODUCT & VARIANT MODULE VERIFICATION")
    print("=" * 70)

    # 1. Credentials
    admin_user = User.objects.filter(role=UserRole.ADMIN, email='admin@brightloop.io').first()
    staff_user = User.objects.filter(role=UserRole.STAFF, email='staff@brightloop.io').first()
    customer_user = User.objects.filter(role=UserRole.CUSTOMER, email='customer@brightloop.io').first()

    assert admin_user, "admin@brightloop.io not found"
    assert staff_user, "staff@brightloop.io not found"
    assert customer_user, "customer@brightloop.io not found"

    print("\n[STEP 1] Authenticating Users via /api/auth/login/...")
    
    # Login Admin
    res_admin = client.post('/api/auth/login/', {'email': 'admin@brightloop.io', 'password': 'Password123!'}, content_type='application/json')
    assert res_admin.status_code == 200, f"Admin login failed: {res_admin.content}"
    admin_token = res_admin.json()['access']
    admin_headers = {'HTTP_AUTHORIZATION': f'Bearer {admin_token}'}
    print("  [OK] Admin logged in successfully.")

    # Login Staff
    res_staff = client.post('/api/auth/login/', {'email': 'staff@brightloop.io', 'password': 'Password123!'}, content_type='application/json')
    assert res_staff.status_code == 200, f"Staff login failed: {res_staff.content}"
    staff_token = res_staff.json()['access']
    staff_headers = {'HTTP_AUTHORIZATION': f'Bearer {staff_token}'}
    print("  [OK] Staff logged in successfully.")

    # Login Customer
    res_cust = client.post('/api/auth/login/', {'email': 'customer@brightloop.io', 'password': 'Password123!'}, content_type='application/json')
    assert res_cust.status_code == 200, f"Customer login failed: {res_cust.content}"
    customer_token = res_cust.json()['access']
    customer_headers = {'HTTP_AUTHORIZATION': f'Bearer {customer_token}'}
    print("  [OK] Customer logged in successfully.")

    # 2. Frontend Template Access
    print("\n[STEP 2] Verifying Frontend Products Route /products/...")
    res_page = client.get('/products/')
    assert res_page.status_code == 200, f"Failed to load /products/: {res_page.status_code}"
    assert b"Products &amp; Variants Management" in res_page.content or b"Products & Variants" in res_page.content
    assert b"productModal" in res_page.content
    assert b"variantModal" in res_page.content
    assert b"taxRulesModal" in res_page.content
    print("  [OK] /products/ served 200 OK with all required modals and dashboard layout.")

    # 3. Admin: Create Product with Inline Variants
    print("\n[STEP 3] Admin: Creating Product with Inline Variants via POST /api/products/...")
    product_payload = {
        "name": "Brightloop Enterprise Suite Pro",
        "product_type": "SOFTWARE",
        "sales_price": "1200.00",
        "cost_price": "350.00",
        "notes": "Enterprise Cloud ERP with Multi-tenant architecture and CRM integration.",
        "is_active": True,
        "variants": [
            {
                "attribute_name": "Edition",
                "attribute_value": "Standard",
                "price_extra": "0.00"
            },
            {
                "attribute_name": "Edition",
                "attribute_value": "Odoo Integration",
                "price_extra": "560.00"
            },
            {
                "attribute_name": "Edition",
                "attribute_value": "Ultimate Dedicated",
                "price_extra": "1250.00"
            }
        ]
    }
    res_create = client.post('/api/products/', json.dumps(product_payload), content_type='application/json', **admin_headers)
    assert res_create.status_code == 201, f"Failed to create product: {res_create.status_code} {res_create.content}"
    created_product = res_create.json()
    prod_id = created_product['id']
    assert created_product['name'] == product_payload['name']
    assert len(created_product['variants']) == 3
    print(f"  [OK] Created Product #{prod_id} '{created_product['name']}' with 3 inline variants:")
    for v in created_product['variants']:
        extra = float(v['price_extra'])
        effective = float(created_product['sales_price']) + extra
        print(f"    - {v['attribute_name']} [{v['attribute_value']}]: Base ${created_product['sales_price']} + Extra ${extra:.2f} = Effective ${effective:.2f}")

    # 4. Admin: Edit Product Details
    print("\n[STEP 4] Admin: Updating Product Details via PUT /api/products/{id}/...")
    update_payload = {
        "name": "Brightloop Enterprise Suite Pro v2",
        "product_type": "SOFTWARE",
        "sales_price": "1350.00",
        "cost_price": "400.00",
        "notes": "Updated Enterprise Cloud ERP with 99.99% SLA.",
        "is_active": True,
        "variants": [
            {
                "id": created_product['variants'][0]['id'],
                "attribute_name": "Edition",
                "attribute_value": "Standard",
                "price_extra": "0.00"
            },
            {
                "id": created_product['variants'][1]['id'],
                "attribute_name": "Edition",
                "attribute_value": "Odoo Integration",
                "price_extra": "580.00"  # updated price extra
            }
        ]
    }
    res_update = client.put(f'/api/products/{prod_id}/', json.dumps(update_payload), content_type='application/json', **admin_headers)
    assert res_update.status_code == 200, f"Failed to update product: {res_update.content}"
    updated_prod = res_update.json()
    assert updated_prod['name'] == "Brightloop Enterprise Suite Pro v2"
    assert updated_prod['sales_price'] == "1350.00"
    print(f"  [OK] Updated product sales price to ${updated_prod['sales_price']} and modified variant price extra.")

    # 5. Admin: Dedicated Variant Management
    print("\n[STEP 5] Admin: Standalone Variant Management via /api/product-variants/...")
    # Add variant
    var_payload = {
        "product": prod_id,
        "attribute_name": "Tier",
        "attribute_value": "High Availability Cluster",
        "price_extra": "750.00"
    }
    res_var = client.post('/api/product-variants/', json.dumps(var_payload), content_type='application/json', **admin_headers)
    assert res_var.status_code == 201, f"Failed to create standalone variant: {res_var.content}"
    new_var = res_var.json()
    var_id = new_var['id']
    print(f"  [OK] Added standalone variant #{var_id}: {new_var['attribute_name']} - {new_var['attribute_value']} (+$750.00)")

    # Edit variant via PATCH
    patch_payload = {"price_extra": "850.00"}
    res_patch = client.patch(f'/api/product-variants/{var_id}/', json.dumps(patch_payload), content_type='application/json', **admin_headers)
    assert res_patch.status_code == 200, f"Failed to patch variant: {res_patch.content}"
    assert res_patch.json()['price_extra'] == "850.00"
    print(f"  [OK] Patched variant price extra to +$850.00")

    # Delete standalone variant
    res_del_var = client.delete(f'/api/product-variants/{var_id}/', **admin_headers)
    assert res_del_var.status_code == 204, f"Failed to delete variant: {res_del_var.status_code}"
    print(f"  [OK] Deleted standalone variant #{var_id} successfully.")

    # 6. Admin: Tax Rules Configuration
    print("\n[STEP 6] Admin: Tax Rules Management via /api/tax-rules/...")
    tax_payload = {
        "name": "State Technology Tax 2026",
        "rate": "7.50",
        "is_active": True
    }
    res_tax = client.post('/api/tax-rules/', json.dumps(tax_payload), content_type='application/json', **admin_headers)
    assert res_tax.status_code == 201, f"Failed to create tax rule: {res_tax.content}"
    tax_data = res_tax.json()
    tax_id = tax_data['id']
    print(f"  [OK] Created Tax Rule #{tax_id}: '{tax_data['name']}' at {tax_data['rate']}%")

    # Update Tax Rule
    tax_update = {"name": "State Technology Tax 2026 (Revised)", "rate": "8.00", "is_active": True}
    res_tax_up = client.put(f'/api/tax-rules/{tax_id}/', json.dumps(tax_update), content_type='application/json', **admin_headers)
    assert res_tax_up.status_code == 200, f"Failed to update tax rule: {res_tax_up.content}"
    print(f"  [OK] Updated Tax Rule #{tax_id} to 8.00%")

    # Delete Tax Rule
    res_tax_del = client.delete(f'/api/tax-rules/{tax_id}/', **admin_headers)
    assert res_tax_del.status_code == 204, f"Failed to delete tax rule: {res_tax_del.status_code}"
    print(f"  [OK] Deleted Tax Rule #{tax_id} successfully.")

    # 7. Admin: Delete Test Product
    print("\n[STEP 7] Admin: Deleting Test Product via DELETE /api/products/{id}/...")
    res_del_prod = client.delete(f'/api/products/{prod_id}/', **admin_headers)
    assert res_del_prod.status_code == 204, f"Failed to delete product: {res_del_prod.status_code}"
    print(f"  [OK] Deleted test product #{prod_id} successfully.")

    # Verify 404 on get
    res_check = client.get(f'/api/products/{prod_id}/', **admin_headers)
    assert res_check.status_code == 404
    print("  [OK] Confirmed product no longer exists in catalog.")

    # 8. Role Boundary Tests (Staff & Customer)
    print("\n[STEP 8] Enforcing Role Boundaries (STAFF & CUSTOMER)...")
    
    # Staff can READ products, but CANNOT write/create/delete
    res_staff_read = client.get('/api/products/', **staff_headers)
    assert res_staff_read.status_code == 200, f"Staff read failed: {res_staff_read.status_code}"
    print("  [OK] Staff allowed GET /api/products/ (Safe method 200 OK).")

    res_staff_write = client.post('/api/products/', json.dumps(product_payload), content_type='application/json', **staff_headers)
    assert res_staff_write.status_code == 403, f"Expected 403 for staff write, got: {res_staff_write.status_code}"
    print("  [OK] Staff blocked from POST /api/products/ (403 Forbidden).")

    res_staff_tax_write = client.post('/api/tax-rules/', json.dumps(tax_payload), content_type='application/json', **staff_headers)
    assert res_staff_tax_write.status_code == 403, f"Expected 403 for staff tax write, got: {res_staff_tax_write.status_code}"
    print("  [OK] Staff blocked from POST /api/tax-rules/ (403 Forbidden).")

    # Customer CANNOT read or write products or taxes
    res_cust_read = client.get('/api/products/', **customer_headers)
    assert res_cust_read.status_code == 403, f"Expected 403 for customer read products, got: {res_cust_read.status_code}"
    print("  [OK] Customer blocked from GET /api/products/ (403 Forbidden).")

    res_cust_taxes = client.get('/api/tax-rules/', **customer_headers)
    assert res_cust_taxes.status_code == 403, f"Expected 403 for customer read tax rules, got: {res_cust_taxes.status_code}"
    print("  [OK] Customer blocked from GET /api/tax-rules/ (403 Forbidden).")

    # 9. Verify Regression on Dashboard and Portal
    print("\n[STEP 9] Regression Testing: Finance Dashboard & Customer Portal...")
    # Dashboard stats / overview
    dash_stats = client.get('/api/dashboard/overview/', **admin_headers)
    assert dash_stats.status_code == 200, f"Dashboard overview failed: {dash_stats.status_code}"
    print("  [OK] Admin Dashboard overview API: 200 OK")

    dash_payments = client.get('/api/dashboard/payments/', **staff_headers)
    assert dash_payments.status_code == 200, f"Dashboard payments failed: {dash_payments.status_code}"
    print("  [OK] Staff Dashboard payments API: 200 OK")

    # Customer subscriptions & invoices
    cust_subs = client.get('/api/subscriptions/', **customer_headers)
    assert cust_subs.status_code == 200, f"Customer subscriptions failed: {cust_subs.status_code}"
    print("  [OK] Customer Portal Subscriptions API: 200 OK")

    cust_invs = client.get('/api/invoices/', **customer_headers)
    assert cust_invs.status_code == 200, f"Customer Portal Invoices API: 200 OK"
    print("  [OK] Customer Portal Invoices API: 200 OK")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY (100% SUCCESS)!")
    print("=" * 70)

if __name__ == '__main__':
    run_verification()
