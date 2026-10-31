from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    BillingPeriod,
    Discount,
    DiscountType,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    Plan,
    Product,
    ProductType,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
    SubscriptionStatus,
    TaxRule,
    UserRole,
)

User = get_user_model()


class BrightloopAPITests(APITestCase):
    def setUp(self):
        # Create users for all three roles
        self.admin_user = User.objects.create_user(
            email='admin@brightloop.io',
            password='Password123!',
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.staff_user = User.objects.create_user(
            email='staff@brightloop.io',
            password='Password123!',
            role=UserRole.STAFF,
            is_staff=False
        )
        self.customer1 = User.objects.create_user(
            email='customer1@example.com',
            password='Password123!',
            role=UserRole.CUSTOMER
        )
        self.customer2 = User.objects.create_user(
            email='customer2@example.com',
            password='Password123!',
            role=UserRole.CUSTOMER
        )

        # Baseline plan
        self.plan = Plan.objects.create(
            name='Pro Plan',
            price=Decimal('49.99'),
            billing_period=BillingPeriod.MONTHLY
        )

        # Baseline tax rule
        self.tax_rule = TaxRule.objects.create(
            name='Standard VAT',
            rate=Decimal('20.00')
        )

        # Baseline product and variant
        self.product = Product.objects.create(
            name='Cloud Storage',
            product_type=ProductType.SOFTWARE,
            sales_price=Decimal('100.00'),
            cost_price=Decimal('40.00')
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            attribute_name='Capacity',
            attribute_value='1TB',
            price_extra=Decimal('25.00')
        )

        # Baseline discount
        self.discount = Discount.objects.create(
            code='SAVE10',
            discount_type=DiscountType.PERCENTAGE,
            value=Decimal('10.00'),
            start_date=timezone.localdate() - timezone.timedelta(days=1),
            end_date=timezone.localdate() + timezone.timedelta(days=30)
        )

    # ==========================================
    # 1. CATALOG PERMISSION TESTS
    # ==========================================

    def test_catalog_admin_write_staff_read(self):
        self.client.force_authenticate(user=self.staff_user)
        res_get = self.client.get('/api/products/')
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)

        res_get_tax = self.client.get('/api/tax-rules/')
        self.assertEqual(res_get_tax.status_code, status.HTTP_200_OK)

        res_get_plans = self.client.get('/api/plans/')
        self.assertEqual(res_get_plans.status_code, status.HTTP_200_OK)

        res_get_discounts = self.client.get('/api/discounts/')
        self.assertEqual(res_get_discounts.status_code, status.HTTP_200_OK)

        # Staff CANNOT write (POST, PUT, DELETE)
        res_post = self.client.post('/api/products/', {
            'name': 'Staff Product',
            'product_type': ProductType.SERVICE,
            'sales_price': '50.00',
            'cost_price': '20.00'
        })
        self.assertEqual(res_post.status_code, status.HTTP_403_FORBIDDEN)

        res_disc_post = self.client.post('/api/discounts/', {
            'code': 'STAFFDISC',
            'discount_type': DiscountType.FIXED,
            'value': '15.00',
            'start_date': str(timezone.localdate()),
            'end_date': str(timezone.localdate() + timezone.timedelta(days=10))
        })
        self.assertEqual(res_disc_post.status_code, status.HTTP_403_FORBIDDEN)

        # Customer CANNOT read or write catalog
        self.client.force_authenticate(user=self.customer1)
        self.assertEqual(self.client.get('/api/products/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/tax-rules/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/plans/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/discounts/').status_code, status.HTTP_403_FORBIDDEN)

        # Admin CAN create
        self.client.force_authenticate(user=self.admin_user)
        res_admin_prod = self.client.post('/api/products/', {
            'name': 'Admin Product',
            'product_type': ProductType.SOFTWARE,
            'sales_price': '150.00',
            'cost_price': '60.00',
            'variants': [
                {
                    'attribute_name': 'Tier',
                    'attribute_value': 'Enterprise',
                    'price_extra': '50.00'
                }
            ]
        }, format='json')
        self.assertEqual(res_admin_prod.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.filter(name='Admin Product').count(), 1)
        self.assertEqual(ProductVariant.objects.filter(attribute_value='Enterprise').count(), 1)

    # ==========================================
    # 2. QUOTATION TEMPLATE TESTS
    # ==========================================

    def test_quotation_template_creation_by_staff_and_admin(self):
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.post('/api/quotation-templates/', {
            'name': 'Standard Quote Template',
            'plan': self.plan.id,
            'validity_days': 45,
            'lines': [
                {
                    'product': self.product.id,
                    'variant': self.variant.id,
                    'quantity': 3
                }
            ]
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        tmpl_id = res.data['id']
        template = QuotationTemplate.objects.get(id=tmpl_id)
        self.assertEqual(template.lines.count(), 1)
        line = template.lines.first()
        self.assertEqual(line.unit_price, Decimal('125.00'))

        self.client.force_authenticate(user=self.customer1)
        res_cust = self.client.get('/api/quotation-templates/')
        self.assertEqual(res_cust.status_code, status.HTTP_403_FORBIDDEN)

    # ==========================================
    # 3. SUBSCRIPTION CRUD & PERMISSIONS
    # ==========================================

    def test_subscription_creation_and_ownership(self):
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.post('/api/subscriptions/', {
            'customer': self.customer1.id,
            'plan': self.plan.id,
            'start_date': '2026-11-01',
            'lines': [
                {
                    'product': self.product.id,
                    'variant': self.variant.id,
                    'quantity': 2
                }
            ]
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        sub_id = res.data['id']
        sub_num = res.data['subscription_number']

        self.assertTrue(sub_num.startswith('SUB-2026-'))
        self.assertEqual(res.data['status'], SubscriptionStatus.DRAFT)
        self.assertEqual(len(res.data['lines']), 1)
        self.assertEqual(Decimal(res.data['lines'][0]['unit_price']), Decimal('125.00'))
        self.assertEqual(Decimal(res.data['lines'][0]['subtotal']), Decimal('250.00'))

        # Customer1 can list and view their own subscription
        self.client.force_authenticate(user=self.customer1)
        res_list = self.client.get('/api/subscriptions/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)
        self.assertEqual(res_list.data[0]['id'], sub_id)

        res_detail = self.client.get(f'/api/subscriptions/{sub_id}/')
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)

        # Customer1 CANNOT edit or delete subscription
        res_patch = self.client.patch(f'/api/subscriptions/{sub_id}/', {'payment_terms_days': 15})
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

        res_delete = self.client.delete(f'/api/subscriptions/{sub_id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_403_FORBIDDEN)

        # Customer2 CANNOT see Customer1's subscription
        self.client.force_authenticate(user=self.customer2)
        res_cust2_list = self.client.get('/api/subscriptions/')
        self.assertEqual(res_cust2_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_cust2_list.data), 0)

        res_cust2_detail = self.client.get(f'/api/subscriptions/{sub_id}/')
        self.assertIn(res_cust2_detail.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_sequential_subscription_number_generation(self):
        self.client.force_authenticate(user=self.staff_user)
        sub1 = self.client.post('/api/subscriptions/', {
            'customer': self.customer1.id,
            'plan': self.plan.id,
            'start_date': '2026-11-01',
        }, format='json')
        self.assertEqual(sub1.status_code, status.HTTP_201_CREATED)

        sub2 = self.client.post('/api/subscriptions/', {
            'customer': self.customer1.id,
            'plan': self.plan.id,
            'start_date': '2026-11-01',
        }, format='json')
        self.assertEqual(sub2.status_code, status.HTTP_201_CREATED)

        num1 = sub1.data['subscription_number']
        num2 = sub2.data['subscription_number']
        seq1 = int(num1.split('-')[2])
        seq2 = int(num2.split('-')[2])
        self.assertEqual(seq2, seq1 + 1)

    # ==========================================
    # 4. TRANSITION ACTION & ACTIVE BILLING DATE
    # ==========================================

    def test_subscription_transitions_and_active_billing_date(self):
        sub = Subscription.objects.create(
            subscription_number='SUB-2026-0099',
            customer=self.customer1,
            plan=self.plan,
            status=SubscriptionStatus.DRAFT,
            start_date=timezone.localdate()
        )

        self.client.force_authenticate(user=self.staff_user)

        # Invalid jump: DRAFT -> ACTIVE must return 400
        res_invalid = self.client.post(f'/api/subscriptions/{sub.id}/transition/', {
            'status': SubscriptionStatus.ACTIVE
        })
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubscriptionStatus.DRAFT)

        # Valid transitions: DRAFT -> QUOTATION -> CONFIRMED -> ACTIVE
        res_quote = self.client.post(f'/api/subscriptions/{sub.id}/transition/', {
            'status': SubscriptionStatus.QUOTATION
        })
        self.assertEqual(res_quote.status_code, status.HTTP_200_OK)

        res_conf = self.client.post(f'/api/subscriptions/{sub.id}/transition/', {
            'status': SubscriptionStatus.CONFIRMED
        })
        self.assertEqual(res_conf.status_code, status.HTTP_200_OK)

        # Moving to ACTIVE must set next_billing_date = start_date
        res_active = self.client.post(f'/api/subscriptions/{sub.id}/transition/', {
            'status': SubscriptionStatus.ACTIVE
        })
        self.assertEqual(res_active.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(sub.next_billing_date, sub.start_date)

    # ==========================================
    # 5. CREATE FROM TEMPLATE ACTION
    # ==========================================

    def test_create_from_template_action(self):
        template = QuotationTemplate.objects.create(
            name='Enterprise SaaS Template',
            plan=self.plan,
            validity_days=60
        )
        QuotationTemplateLine.objects.create(
            template=template,
            product=self.product,
            variant=self.variant,
            quantity=5,
            unit_price=Decimal('125.00')
        )

        self.client.force_authenticate(user=self.staff_user)
        res = self.client.post('/api/subscriptions/create-from-template/', {
            'template': template.id,
            'customer': self.customer2.id,
            'start_date': '2026-11-15'
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        sub_data = res.data
        self.assertTrue(sub_data['subscription_number'].startswith('SUB-2026-'))
        self.assertEqual(sub_data['customer'], self.customer2.id)
        self.assertEqual(sub_data['plan'], self.plan.id)
        self.assertEqual(sub_data['status'], SubscriptionStatus.DRAFT)
        self.assertEqual(len(sub_data['lines']), 1)
        self.assertEqual(Decimal(sub_data['lines'][0]['unit_price']), Decimal('125.00'))
        self.assertEqual(sub_data['lines'][0]['quantity'], 5)

    # ==========================================
    # 6. INVOICE GENERATION COMMAND TESTS
    # ==========================================

    def test_generate_invoices_command_idempotent_and_summary(self):
        today = timezone.localdate()
        sub = Subscription.objects.create(
            subscription_number='SUB-2026-0501',
            customer=self.customer1,
            plan=self.plan,
            discount=self.discount,
            status=SubscriptionStatus.ACTIVE,
            start_date=today,
            next_billing_date=today
        )
        SubscriptionLine.objects.create(
            subscription=sub,
            product=self.product,
            variant=self.variant,
            quantity=2,
            unit_price=Decimal('125.00'),
            tax_rule=self.tax_rule
        )

        # Run command first time: exactly 1 invoice created
        call_command('generate_invoices', date=str(today))
        self.assertEqual(Invoice.objects.filter(subscription=sub).count(), 1)

        inv = Invoice.objects.get(subscription=sub)
        self.assertTrue(inv.invoice_number.startswith('INV-2026-'))
        self.assertEqual(inv.subtotal, Decimal('250.00'))
        self.assertEqual(inv.tax_amount, Decimal('50.00'))  # 20% of 250
        self.assertEqual(inv.discount_amount, Decimal('25.00'))  # 10% of 250
        self.assertEqual(inv.total_amount, Decimal('275.00'))  # 250 + 50 - 25

        # Verify pricing rule: copied from SubscriptionLines only (Plan.price is NOT billed)
        self.assertEqual(inv.lines.count(), 1)
        line = inv.lines.first()
        self.assertEqual(line.product, self.product)
        self.assertEqual(line.unit_price, Decimal('125.00'))
        self.assertEqual(line.quantity, 2)

        # Verify next_billing_date advanced
        sub.refresh_from_db()
        self.assertGreater(sub.next_billing_date, today)

        # Run command second time: assert one invoice per period, no duplicates created
        call_command('generate_invoices', date=str(today))
        self.assertEqual(Invoice.objects.filter(subscription=sub).count(), 1)

    def test_generate_invoices_discount_usage_limit(self):
        today = timezone.localdate()
        limited_discount = Discount.objects.create(
            code='LIMITED1',
            discount_type=DiscountType.FIXED,
            value=Decimal('50.00'),
            start_date=today - timezone.timedelta(days=1),
            end_date=today + timezone.timedelta(days=10),
            max_uses=1,
            current_uses=0
        )

        sub1 = Subscription.objects.create(
            subscription_number='SUB-2026-0601',
            customer=self.customer1,
            plan=self.plan,
            discount=limited_discount,
            status=SubscriptionStatus.ACTIVE,
            start_date=today,
            next_billing_date=today
        )
        SubscriptionLine.objects.create(
            subscription=sub1,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00')
        )

        sub2 = Subscription.objects.create(
            subscription_number='SUB-2026-0602',
            customer=self.customer2,
            plan=self.plan,
            discount=limited_discount,
            status=SubscriptionStatus.ACTIVE,
            start_date=today,
            next_billing_date=today
        )
        SubscriptionLine.objects.create(
            subscription=sub2,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00')
        )

        # Run invoice generation
        call_command('generate_invoices', date=str(today))

        limited_discount.refresh_from_db()
        self.assertEqual(limited_discount.current_uses, 1)

        inv1 = Invoice.objects.get(subscription=sub1)
        inv2 = Invoice.objects.get(subscription=sub2)

        # Exactly one subscription receives the discount, the other is not discounted due to usage limit
        discounted = [inv for inv in [inv1, inv2] if inv.discount_amount > Decimal('0.00')]
        non_discounted = [inv for inv in [inv1, inv2] if inv.discount_amount == Decimal('0.00')]
        self.assertEqual(len(discounted), 1)
        self.assertEqual(len(non_discounted), 1)
        self.assertEqual(discounted[0].discount_amount, Decimal('50.00'))

    def test_generate_invoices_skips_paused_and_closed(self):
        today = timezone.localdate()
        paused_sub = Subscription.objects.create(
            subscription_number='SUB-2026-PAUSED',
            customer=self.customer1,
            plan=self.plan,
            status=SubscriptionStatus.PAUSED,
            start_date=today,
            next_billing_date=today
        )
        SubscriptionLine.objects.create(
            subscription=paused_sub,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00')
        )

        closed_sub = Subscription.objects.create(
            subscription_number='SUB-2026-CLOSED',
            customer=self.customer1,
            plan=self.plan,
            status=SubscriptionStatus.CLOSED,
            start_date=today,
            next_billing_date=today
        )
        SubscriptionLine.objects.create(
            subscription=closed_sub,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00')
        )

        call_command('generate_invoices', date=str(today))
        self.assertFalse(Invoice.objects.filter(subscription=paused_sub).exists())
        self.assertFalse(Invoice.objects.filter(subscription=closed_sub).exists())

    def test_generate_invoices_auto_close_at_end(self):
        today = timezone.localdate()
        closing_plan = Plan.objects.create(
            name='Fixed Term Plan',
            price=Decimal('10.00'),
            billing_period=BillingPeriod.DAILY,
            auto_close_at_end=True
        )
        expiring_sub = Subscription.objects.create(
            subscription_number='SUB-2026-EXPIRE',
            customer=self.customer1,
            plan=closing_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=today,
            expiry_date=today,
            next_billing_date=today
        )
        SubscriptionLine.objects.create(
            subscription=expiring_sub,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00')
        )

        call_command('generate_invoices', date=str(today))
        expiring_sub.refresh_from_db()
        self.assertEqual(expiring_sub.status, SubscriptionStatus.CLOSED)

    # ==========================================
    # 7. INVOICE ENDPOINTS: CONFIRM, CANCEL, SEND, PDF, ISOLATION
    # ==========================================

    def test_invoice_endpoints_and_isolation(self):
        today = timezone.localdate()
        invoice = Invoice.objects.create(
            invoice_number='INV-2026-9001',
            customer=self.customer1,
            status=InvoiceStatus.DRAFT,
            issue_date=today,
            due_date=today + timezone.timedelta(days=30),
            billing_period_start=today,
            billing_period_end=today + timezone.timedelta(days=30),
            subtotal=Decimal('200.00'),
            tax_amount=Decimal('40.00'),
            total_amount=Decimal('240.00')
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            product=self.product,
            description='Cloud Storage License',
            quantity=2,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('200.00'),
            tax_rate=Decimal('20.00'),
            tax_amount=Decimal('40.00'),
            total=Decimal('240.00')
        )

        # Customer2 CANNOT view Customer1's invoice
        self.client.force_authenticate(user=self.customer2)
        res_cust2_list = self.client.get('/api/invoices/')
        self.assertEqual(res_cust2_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_cust2_list.data), 0)

        res_cust2_detail = self.client.get(f'/api/invoices/{invoice.id}/')
        self.assertIn(res_cust2_detail.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        # Customer1 CAN view their own invoice
        self.client.force_authenticate(user=self.customer1)
        res_cust1 = self.client.get(f'/api/invoices/{invoice.id}/')
        self.assertEqual(res_cust1.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cust1.data['invoice_number'], 'INV-2026-9001')

        # Customer1 CAN download / print PDF of their own invoice
        res_pdf = self.client.get(f'/api/invoices/{invoice.id}/pdf/')
        self.assertEqual(res_pdf.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(res_pdf.content.startswith(b'%PDF-1.4'))

        # Print alias
        res_print = self.client.get(f'/api/invoices/{invoice.id}/print/')
        self.assertEqual(res_print.status_code, status.HTTP_200_OK)

        # Staff can confirm invoice
        self.client.force_authenticate(user=self.staff_user)
        res_conf = self.client.post(f'/api/invoices/{invoice.id}/confirm/')
        self.assertEqual(res_conf.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CONFIRMED)

        # Staff can send invoice via email (console backend)
        mail.outbox.clear()
        res_send = self.client.post(f'/api/invoices/{invoice.id}/send/')
        self.assertEqual(res_send.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invoice.invoice_number, mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.customer1.email])

        # Staff can cancel invoice
        res_cancel = self.client.post(f'/api/invoices/{invoice.id}/cancel/')
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CANCELLED)

    # ==========================================
    # 8. PAYMENT ENDPOINT TESTS (POST ONLY, STAFF/ADMIN)
    # ==========================================

    def test_payment_endpoint_post_only_staff_admin(self):
        today = timezone.localdate()
        invoice = Invoice.objects.create(
            invoice_number='INV-2026-PAY1',
            customer=self.customer1,
            status=InvoiceStatus.CONFIRMED,
            issue_date=today,
            due_date=today + timezone.timedelta(days=30),
            billing_period_start=today,
            billing_period_end=today + timezone.timedelta(days=30),
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0.00'),
            total_amount=Decimal('100.00')
        )

        # GET on /api/payments/ returns 405 Method Not Allowed (POST only)
        self.client.force_authenticate(user=self.staff_user)
        res_get_payments = self.client.get('/api/payments/')
        self.assertEqual(res_get_payments.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Customer CANNOT create payment (403 Forbidden)
        self.client.force_authenticate(user=self.customer1)
        res_cust_pay = self.client.post('/api/payments/', {
            'invoice': invoice.id,
            'amount': '50.00',
            'method': PaymentMethod.BANK_TRANSFER
        })
        self.assertEqual(res_cust_pay.status_code, status.HTTP_403_FORBIDDEN)

        # Staff creates partial payment of $50
        self.client.force_authenticate(user=self.staff_user)
        res_pay1 = self.client.post('/api/payments/', {
            'invoice': invoice.id,
            'amount': '50.00',
            'method': PaymentMethod.CREDIT_CARD,
            'transaction_reference': 'TXN-001'
        })
        self.assertEqual(res_pay1.status_code, status.HTTP_201_CREATED)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.CONFIRMED)
        self.assertEqual(invoice.amount_paid, Decimal('50.00'))
        self.assertEqual(invoice.amount_due, Decimal('50.00'))

        # Overpayment rejected (attempting to pay $60 when $50 due)
        res_overpay = self.client.post('/api/payments/', {
            'invoice': invoice.id,
            'amount': '60.00',
            'method': PaymentMethod.CREDIT_CARD
        })
        self.assertEqual(res_overpay.status_code, status.HTTP_400_BAD_REQUEST)

        # Settle the remaining balance ($50) -> transitions invoice to PAID automatically
        res_pay2 = self.client.post('/api/payments/', {
            'invoice': invoice.id,
            'amount': '50.00',
            'method': PaymentMethod.BANK_TRANSFER,
            'transaction_reference': 'TXN-002'
        })
        self.assertEqual(res_pay2.status_code, status.HTTP_201_CREATED)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(invoice.amount_due, Decimal('0.00'))

    # ==========================================
    # 9. AUTH ME & CORS TESTS
    # ==========================================

    def test_auth_me_endpoint(self):
        # Unauthenticated returns 401
        res_unauth = self.client.get('/api/auth/me/')
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated customer
        self.client.force_authenticate(user=self.customer1)
        res_me = self.client.get('/api/auth/me/')
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)
        self.assertEqual(res_me.data['id'], self.customer1.id)
        self.assertEqual(res_me.data['email'], self.customer1.email)
        self.assertEqual(res_me.data['role'], UserRole.CUSTOMER)
        self.assertIn('first_name', res_me.data)
        self.assertIn('last_name', res_me.data)

        # Authenticated staff
        self.client.force_authenticate(user=self.staff_user)
        res_staff = self.client.get('/api/auth/me/')
        self.assertEqual(res_staff.status_code, status.HTTP_200_OK)
        self.assertEqual(res_staff.data['role'], UserRole.STAFF)

    def test_cors_headers(self):
        for origin in ['http://localhost:5173', 'http://127.0.0.1:5500', 'http://localhost:3000']:
            res = self.client.get('/api/products/', HTTP_ORIGIN=origin)
            self.assertEqual(res.headers.get('Access-Control-Allow-Origin'), origin)

        # Disallowed origin
        res_bad = self.client.get('/api/products/', HTTP_ORIGIN='http://evil.com')
        self.assertNotEqual(res_bad.headers.get('Access-Control-Allow-Origin'), 'http://evil.com')
