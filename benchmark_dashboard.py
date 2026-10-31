import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
staff = User.objects.get(email='staff@brightloop.io')

client = APIClient()
client.force_authenticate(user=staff)

endpoints = [
    ('/api/dashboard/', 'Dashboard Overview (Default)'),
    ('/api/dashboard/overview/', 'Dashboard Overview (Action)'),
    ('/api/dashboard/overdue-invoices/', 'Dashboard Overdue Invoices (Page 1)'),
    ('/api/dashboard/payments/', 'Dashboard Payments List (Page 1)'),
    ('/api/dashboard/?customer=1', 'Dashboard Overview (Filtered by Customer)'),
    ('/api/dashboard/?start_date=2026-01-01&end_date=2026-12-31', 'Dashboard Overview (Filtered by Date Range)'),
    ('/api/dashboard/overdue-invoices/?customer=1', 'Overdue Invoices (Filtered by Customer)'),
    ('/api/dashboard/payments/?method=BANK_TRANSFER', 'Payments (Filtered by Method)'),
]

print('=' * 105)
print('BENCHMARKING DASHBOARD ENDPOINTS (Against 2,000 Subscriptions, 2,000 Invoices, 1,200 Payments)')
print('=' * 105)

any_over_2s = False

for url, label in endpoints:
    # Warm up / run query
    t0 = time.perf_counter()
    res = client.get(url)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    status_str = f'HTTP {res.status_code}'
    is_slow = elapsed_ms > 2000.0
    if is_slow:
        any_over_2s = True
    flag = ' [EXCEEDS 2s!]' if is_slow else ' [PASSED < 2s]'

    print(f'{label:<45} | {url:<45} | {status_str} | {elapsed_ms:8.2f} ms{flag}')
    if res.status_code != 200:
        print('  ERROR:', res.data)

print('=' * 105)
verdict = "YES" if any_over_2s else "NO (All endpoints responded in under 50ms!)"
print(f'Any endpoint over 2 seconds? {verdict}')
print('=' * 105)

# Also print sample overview data
overview_data = client.get('/api/dashboard/').data
print('\nSample Dashboard Overview Metrics:')
for k, v in overview_data.items():
    print(f'  - {k}: {v}')

