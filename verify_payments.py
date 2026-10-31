import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, UserRole, Invoice, InvoiceStatus, Payment, PaymentMethod

def test_payments():
    print("=================================================================")
    print("VERIFYING PAYMENT WORKFLOW AND VALIDATION RULES")
    print("=================================================================")

    # 1. Setup admin/staff client and customer
    admin = User.objects.filter(role=UserRole.ADMIN).first()
    customer = User.objects.filter(role=UserRole.CUSTOMER).first()

    client = APIClient()
    client.force_authenticate(user=admin)

    # Create a fresh confirmed invoice with total $300.00
    inv = Invoice.objects.create(
        invoice_number="INV-TEST-PAY-001",
        customer=customer,
        status=InvoiceStatus.CONFIRMED,
        issue_date=timezone.localdate(),
        due_date=timezone.localdate() + timezone.timedelta(days=30),
        billing_period_start=timezone.localdate(),
        billing_period_end=timezone.localdate() + timezone.timedelta(days=30),
        subtotal=Decimal('250.00'),
        tax_amount=Decimal('50.00'),
        discount_amount=Decimal('0.00'),
        total_amount=Decimal('300.00')
    )

    print(f"Created Test Invoice {inv.invoice_number}: Total = ${inv.total_amount}, Status = {inv.status}")

    # TEST A: Outstanding amount initially
    assert inv.amount_paid == Decimal('0.00'), f"Expected amount_paid 0.00, got {inv.amount_paid}"
    assert inv.amount_due == Decimal('300.00'), f"Expected amount_due 300.00, got {inv.amount_due}"
    print("[PASSED] Initial outstanding amount correctly calculated ($300.00)")

    # TEST B: Overpayment is rejected
    res_overpay = client.post('/api/payments/', {
        'invoice': inv.id,
        'amount': '350.00',
        'method': PaymentMethod.CREDIT_CARD,
        'note': 'Attempted overpayment'
    }, format='json')
    assert res_overpay.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for overpayment, got {res_overpay.status_code}: {res_overpay.data}"
    print(f"[PASSED] Overpayment of $350.00 rejected: {res_overpay.data}")

    # TEST C: Partial payment leaves invoice outstanding
    res_partial = client.post('/api/payments/', {
        'invoice': inv.id,
        'amount': '100.00',
        'method': PaymentMethod.BANK_TRANSFER,
        'transaction_reference': 'TX-PARTIAL-100',
        'note': 'First installment'
    }, format='json')
    assert res_partial.status_code == status.HTTP_201_CREATED, f"Expected 201 for partial payment, got {res_partial.status_code}: {res_partial.data}"

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.CONFIRMED, f"Expected status CONFIRMED after partial payment, got {inv.status}"
    assert inv.amount_paid == Decimal('100.00'), f"Expected amount_paid 100.00, got {inv.amount_paid}"
    assert inv.amount_due == Decimal('200.00'), f"Expected amount_due 200.00, got {inv.amount_due}"
    print(f"[PASSED] Partial payment of $100.00 processed. Status remains {inv.status}, Outstanding = ${inv.amount_due}")

    # TEST D: Verify payment fields saved (method, amount, date, note, reference)
    p1 = Payment.objects.get(id=res_partial.data['id'])
    assert p1.amount == Decimal('100.00'), f"Expected 100.00, got {p1.amount}"
    assert p1.method == PaymentMethod.BANK_TRANSFER, f"Expected BANK_TRANSFER, got {p1.method}"
    assert p1.transaction_reference == 'TX-PARTIAL-100', f"Expected TX-PARTIAL-100, got {p1.transaction_reference}"
    assert p1.note == 'First installment', f"Expected 'First installment', got {p1.note}"
    assert p1.payment_date is not None, "payment_date is None"
    print(f"[PASSED] Payment details saved accurately: method={p1.method}, amount={p1.amount}, date={p1.payment_date}, note={p1.note}")

    # TEST E: Second overpayment attempt (amount > remaining $200.00)
    res_overpay2 = client.post('/api/payments/', {
        'invoice': inv.id,
        'amount': '200.01',
        'method': PaymentMethod.CASH,
    }, format='json')
    assert res_overpay2.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for second overpayment, got {res_overpay2.status_code}: {res_overpay2.data}"
    print(f"[PASSED] Second overpayment ($200.01 against $200.00 balance) rejected: {res_overpay2.data}")

    # TEST F: Full payment of remaining balance changes invoice status to PAID
    res_full = client.post('/api/payments/', {
        'invoice': inv.id,
        'amount': '200.00',
        'method': PaymentMethod.CREDIT_CARD,
        'transaction_reference': 'TX-FINAL-200',
        'note': 'Settling final balance'
    }, format='json')
    assert res_full.status_code == status.HTTP_201_CREATED, f"Expected 201 for full settlement, got {res_full.status_code}: {res_full.data}"

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID, f"Expected status PAID after full payment, got {inv.status}"
    assert inv.amount_paid == Decimal('300.00'), f"Expected amount_paid 300.00, got {inv.amount_paid}"
    assert inv.amount_due == Decimal('0.00'), f"Expected amount_due 0.00, got {inv.amount_due}"
    print(f"[PASSED] Final payment of $200.00 processed. Invoice status transitioned to {inv.status}, Outstanding = ${inv.amount_due}")

    # TEST G: Payment against already PAID invoice is rejected
    res_after_paid = client.post('/api/payments/', {
        'invoice': inv.id,
        'amount': '10.00',
        'method': PaymentMethod.CASH
    }, format='json')
    assert res_after_paid.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 when paying PAID invoice, got {res_after_paid.status_code}"
    print(f"[PASSED] Payment against settled invoice rejected: {res_after_paid.data}")

    print("=================================================================")
    print("ALL PAYMENT VALIDATION TESTS PASSED PERFECTLY!")
    print("=================================================================")

if __name__ == '__main__':
    test_payments()

