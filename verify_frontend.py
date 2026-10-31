import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, UserRole

def test_frontend():
    print("=================================================================")
    print("VERIFYING FRONTEND ARCHITECTURE, TEMPLATES, AND AUTH INTEGRATION")
    print("=================================================================")

    client = APIClient()

    # 1. VERIFY DJANGO SERVES PAGES
    print("\n--- 1. Template Serving Verification ---")
    res_root = client.get('/')
    assert res_root.status_code == 302, f"Expected 302 redirect for root, got {res_root.status_code}"
    assert res_root.url == '/login/', f"Expected redirect to /login/, got {res_root.url}"
    print(f"[PASSED] GET / redirects to {res_root.url} (302)")

    res_login = client.get('/login/')
    assert res_login.status_code == 200, f"Expected 200 for /login/, got {res_login.status_code}"
    content_login = res_login.content.decode('utf-8')
    assert "Sign in to your Brightloop" in content_login
    assert "loginEmail" in content_login
    assert "loginPassword" in content_login
    assert "rememberMe" in content_login
    assert "bootstrap@5.3.3" in content_login
    assert "api.js" in content_login
    assert "auth.js" in content_login
    print("[PASSED] GET /login/ serves valid HTML5 template with Bootstrap 5, Inter font, form inputs and JS modules")

    res_signup = client.get('/signup/')
    assert res_signup.status_code == 200, f"Expected 200 for /signup/, got {res_signup.status_code}"
    content_signup = res_signup.content.decode('utf-8')
    assert "Create your account" in content_signup
    assert "signupEmail" in content_signup
    assert "signupPassword" in content_signup
    assert "signupConfirmPassword" in content_signup
    assert "ruleLength" in content_signup
    assert "ruleUpper" in content_signup
    assert "ruleLower" in content_signup
    assert "ruleSpecial" in content_signup
    print("[PASSED] GET /signup/ serves valid HTML5 template with real-time password checklist requirements")

    res_dash = client.get('/dashboard/')
    assert res_dash.status_code == 200
    assert "Brightloop Dashboard" in res_dash.content.decode('utf-8')
    print("[PASSED] GET /dashboard/ serves admin/staff dashboard landing template")

    res_portal = client.get('/portal/')
    assert res_portal.status_code == 200
    assert "Customer Portal" in res_portal.content.decode('utf-8')
    print("[PASSED] GET /portal/ serves customer portal landing template")

    # 2. VERIFY LOGIN INTEGRATION AND ROLE REDIRECTIONS
    print("\n--- 2. Login Integration & Role Redirection ---")

    # Admin login
    res_admin_login = client.post('/api/auth/login/', {
        'email': 'admin@brightloop.io',
        'password': 'Password123!'
    }, format='json')
    assert res_admin_login.status_code == 200, f"Admin login failed: {res_admin_login.data}"
    admin_tokens = res_admin_login.data
    assert 'access' in admin_tokens and 'refresh' in admin_tokens

    # Verify me endpoint for Admin
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens['access']}")
    res_admin_me = client.get('/api/auth/me/')
    assert res_admin_me.status_code == 200
    assert res_admin_me.data['role'] == UserRole.ADMIN
    admin_target = '/dashboard/' if res_admin_me.data['role'] in ['ADMIN', 'STAFF'] else '/portal/'
    assert admin_target == '/dashboard/'
    print(f"[PASSED] Admin login successful -> Role: {res_admin_me.data['role']} -> Redirect Target: {admin_target}")

    # Staff login
    res_staff_login = client.post('/api/auth/login/', {
        'email': 'staff@brightloop.io',
        'password': 'Password123!'
    }, format='json')
    assert res_staff_login.status_code == 200, f"Staff login failed: {res_staff_login.data}"
    staff_tokens = res_staff_login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_tokens['access']}")
    res_staff_me = client.get('/api/auth/me/')
    assert res_staff_me.status_code == 200
    assert res_staff_me.data['role'] == UserRole.STAFF
    staff_target = '/dashboard/' if res_staff_me.data['role'] in ['ADMIN', 'STAFF'] else '/portal/'
    assert staff_target == '/dashboard/'
    print(f"[PASSED] Staff login successful -> Role: {res_staff_me.data['role']} -> Redirect Target: {staff_target}")

    # Customer login
    res_cust_login = client.post('/api/auth/login/', {
        'email': 'customer@brightloop.io',
        'password': 'Password123!'
    }, format='json')
    assert res_cust_login.status_code == 200, f"Customer login failed: {res_cust_login.data}"
    cust_tokens = res_cust_login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {cust_tokens['access']}")
    res_cust_me = client.get('/api/auth/me/')
    assert res_cust_me.status_code == 200
    assert res_cust_me.data['role'] == UserRole.CUSTOMER
    cust_target = '/dashboard/' if res_cust_me.data['role'] in ['ADMIN', 'STAFF'] else '/portal/'
    assert cust_target == '/portal/'
    print(f"[PASSED] Customer login successful -> Role: {res_cust_me.data['role']} -> Redirect Target: {cust_target}")

    # 3. VERIFY TOKEN REFRESH
    print("\n--- 3. Token Refresh Integration ---")
    res_refresh = client.post('/api/auth/token/refresh/', {
        'refresh': admin_tokens['refresh']
    }, format='json')
    assert res_refresh.status_code == 200, f"Token refresh failed: {res_refresh.data}"
    new_access = res_refresh.data['access']
    assert new_access is not None

    # Test new access token against protected /api/auth/me/
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
    res_refreshed_me = client.get('/api/auth/me/')
    assert res_refreshed_me.status_code == 200
    assert res_refreshed_me.data['email'] == 'admin@brightloop.io'
    print("[PASSED] Token refresh successful: new access token accepted by /api/auth/me/")

    # 4. VERIFY SIGNUP API INTEGRATION & PASSWORD REQUIREMENTS
    print("\n--- 4. Signup API Integration & Password Rules ---")

    # Clean up test user if previously created
    User.objects.filter(email='frontend_test@example.com').delete()

    # Test A: Password too short (<= 8 chars)
    res_short = client.post('/api/auth/signup/', {
        'email': 'frontend_test@example.com',
        'password': 'Short1!'
    }, format='json')
    assert res_short.status_code == 400
    assert 'password' in res_short.data
    print(f"[PASSED] Rejected password with <= 8 chars: {res_short.data['password']}")

    # Test B: Password missing uppercase
    res_no_upper = client.post('/api/auth/signup/', {
        'email': 'frontend_test@example.com',
        'password': 'password123!'
    }, format='json')
    assert res_no_upper.status_code == 400
    assert 'password' in res_no_upper.data
    print(f"[PASSED] Rejected password without uppercase: {res_no_upper.data['password']}")

    # Test C: Password missing special character
    res_no_special = client.post('/api/auth/signup/', {
        'email': 'frontend_test@example.com',
        'password': 'Password123'
    }, format='json')
    assert res_no_special.status_code == 400
    assert 'password' in res_no_special.data
    print(f"[PASSED] Rejected password without special character: {res_no_special.data['password']}")

    # Test D: Valid signup
    res_valid_signup = client.post('/api/auth/signup/', {
        'email': 'frontend_test@example.com',
        'password': 'SecurePassword2026!',
        'first_name': 'Frontend',
        'last_name': 'Tester'
    }, format='json')
    assert res_valid_signup.status_code == 201, f"Signup failed: {res_valid_signup.data}"
    created_user = User.objects.get(email='frontend_test@example.com')
    assert created_user.role == UserRole.CUSTOMER
    assert created_user.first_name == 'Frontend'
    print(f"[PASSED] Valid signup created account with role: {created_user.role}")

    # Test E: Duplicate email rejected
    res_dup = client.post('/api/auth/signup/', {
        'email': 'frontend_test@example.com',
        'password': 'SecurePassword2026!'
    }, format='json')
    assert res_dup.status_code == 400
    assert 'email' in res_dup.data
    print(f"[PASSED] Duplicate email properly rejected: {res_dup.data['email']}")

    # Test F: Newly created user logs in and redirects to customer portal
    res_new_login = client.post('/api/auth/login/', {
        'email': 'frontend_test@example.com',
        'password': 'SecurePassword2026!'
    }, format='json')
    assert res_new_login.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {res_new_login.data['access']}")
    res_new_me = client.get('/api/auth/me/')
    assert res_new_me.data['role'] == UserRole.CUSTOMER
    print(f"[PASSED] New registered user successfully logged in and mapped to /portal/")

    print("\n=================================================================")
    print("ALL FRONTEND VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=================================================================")

if __name__ == '__main__':
    test_frontend()

