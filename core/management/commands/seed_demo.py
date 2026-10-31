"""
core/management/commands/seed_demo.py - High-performance demo dataset seeder.
Creates:
- Admin, Staff, and Customer users with known passwords
- 50 demo customers
- 5 catalog products with variants
- 3 recurring plans
- 2000 subscriptions with lines
- 2000+ invoices with lines (including PAID, open CONFIRMED, and OVERDUE)
- Associated payments (full and partial)
"""

import time
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

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
    Subscription,
    SubscriptionLine,
    SubscriptionStatus,
    TaxRule,
    UserRole,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds demo data: 50 customers, 5 products, 3 plans, 2000 subscriptions and invoices with payments and overdue items."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            '--flush',
            action='store_true',
            dest='clean',
            help='Wipes existing demo data before seeding.',
        )

    def handle(self, *args, **options):
        start_time = time.time()
        self.stdout.write(self.style.NOTICE("Initializing demo data seeding..."))

        if options.get('clean'):
            self.stdout.write("Cleaning existing demo data...")
            Payment.objects.all().delete()
            InvoiceLine.objects.all().delete()
            Invoice.objects.all().delete()
            SubscriptionLine.objects.all().delete()
            Subscription.objects.all().delete()
            ProductVariant.objects.all().delete()
            Product.objects.all().delete()
            Plan.objects.all().delete()
            TaxRule.objects.all().delete()
            User.objects.filter(email__contains='demo.com').delete()

        password_hash = make_password('Password123!')
        today = timezone.localdate()

        # 1. Primary Users with Known Passwords
        admin_user, _ = User.objects.get_or_create(
            email='admin@brightloop.io',
            defaults={
                'password': password_hash,
                'role': UserRole.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Admin',
                'last_name': 'User',
            }
        )
        if not admin_user.is_staff or not admin_user.is_superuser:
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.role = UserRole.ADMIN
            admin_user.password = password_hash
            admin_user.save()

        staff_user, _ = User.objects.get_or_create(
            email='staff@brightloop.io',
            defaults={
                'password': password_hash,
                'role': UserRole.STAFF,
                'is_staff': False,
                'first_name': 'Staff',
                'last_name': 'Member',
            }
        )
        staff_user.password = password_hash
        staff_user.save()

        primary_customer, _ = User.objects.get_or_create(
            email='customer@brightloop.io',
            defaults={
                'password': password_hash,
                'role': UserRole.CUSTOMER,
                'is_staff': False,
                'first_name': 'Demo',
                'last_name': 'Customer',
            }
        )
        primary_customer.password = password_hash
        primary_customer.save()

        # 2. 50 Customers
        self.stdout.write("Provisioning 50 demo customer accounts...")
        existing_demo_emails = set(
            User.objects.filter(email__startswith='customer')
            .filter(email__endswith='@demo.com')
            .values_list('email', flat=True)
        )
        customers_to_create = []
        for i in range(1, 51):
            email = f"customer{i}@demo.com"
            if email not in existing_demo_emails:
                customers_to_create.append(
                    User(
                        email=email,
                        password=password_hash,
                        role=UserRole.CUSTOMER,
                        first_name=f"Customer",
                        last_name=f"#{i}",
                        is_active=True
                    )
                )
        if customers_to_create:
            User.objects.bulk_create(customers_to_create)

        customers = list(User.objects.filter(role=UserRole.CUSTOMER).order_by('id')[:50])
        if len(customers) < 50:
            customers.append(primary_customer)

        # 3. Tax Rules
        vat20, _ = TaxRule.objects.get_or_create(
            name='Standard VAT 20%',
            defaults={'rate': Decimal('20.00'), 'is_active': True}
        )
        vat5, _ = TaxRule.objects.get_or_create(
            name='Reduced VAT 5%',
            defaults={'rate': Decimal('5.00'), 'is_active': True}
        )

        # 4. 5 Products & Variants
        self.stdout.write("Setting up 5 catalog products with variants...")
        p1, _ = Product.objects.get_or_create(
            name='Cloud Compute Instance',
            defaults={'product_type': ProductType.SOFTWARE, 'sales_price': Decimal('100.00'), 'cost_price': Decimal('40.00')}
        )
        ProductVariant.objects.get_or_create(
            product=p1, attribute_name='vCPU / RAM', attribute_value='4 Core / 16GB',
            defaults={'price_extra': Decimal('40.00')}
        )
        ProductVariant.objects.get_or_create(
            product=p1, attribute_name='vCPU / RAM', attribute_value='8 Core / 32GB',
            defaults={'price_extra': Decimal('100.00')}
        )

        p2, _ = Product.objects.get_or_create(
            name='Object Storage 1TB',
            defaults={'product_type': ProductType.SOFTWARE, 'sales_price': Decimal('50.00'), 'cost_price': Decimal('15.00')}
        )
        ProductVariant.objects.get_or_create(
            product=p2, attribute_name='Performance', attribute_value='Standard',
            defaults={'price_extra': Decimal('0.00')}
        )
        v2_fast, _ = ProductVariant.objects.get_or_create(
            product=p2, attribute_name='Performance', attribute_value='NVMe HighIOPS',
            defaults={'price_extra': Decimal('25.00')}
        )

        p3, _ = Product.objects.get_or_create(
            name='24/7 Managed DevOps Support',
            defaults={'product_type': ProductType.SERVICE, 'sales_price': Decimal('250.00'), 'cost_price': Decimal('100.00')}
        )

        p4, _ = Product.objects.get_or_create(
            name='Security Gateway Appliance',
            defaults={'product_type': ProductType.HARDWARE, 'sales_price': Decimal('450.00'), 'cost_price': Decimal('220.00')}
        )

        p5, _ = Product.objects.get_or_create(
            name='API Access Credits Pack',
            defaults={'product_type': ProductType.CONSUMABLE, 'sales_price': Decimal('30.00'), 'cost_price': Decimal('5.00')}
        )

        products_list = [p1, p2, p3, p4, p5]

        # 5. 3 Plans
        self.stdout.write("Configuring 3 subscription billing plans...")
        plan_starter, _ = Plan.objects.get_or_create(
            name='Starter Tier',
            defaults={'price': Decimal('29.00'), 'billing_period': BillingPeriod.MONTHLY}
        )
        plan_pro, _ = Plan.objects.get_or_create(
            name='Business Pro Tier',
            defaults={'price': Decimal('99.00'), 'billing_period': BillingPeriod.MONTHLY}
        )
        plan_enterprise, _ = Plan.objects.get_or_create(
            name='Enterprise Annual Tier',
            defaults={'price': Decimal('899.00'), 'billing_period': BillingPeriod.YEARLY}
        )
        plans_list = [plan_starter, plan_pro, plan_enterprise]

        # 6. 2000 Subscriptions with Lines
        self.stdout.write("Generating 2,000 subscriptions and lines...")
        current_sub_count = Subscription.objects.count()
        target_sub_count = 2000
        subs_needed = max(0, target_sub_count - current_sub_count)

        if subs_needed > 0:
            subs_to_create = []
            for i in range(subs_needed):
                idx = current_sub_count + i + 1
                customer = customers[i % len(customers)]
                plan = plans_list[i % len(plans_list)]

                # Status distribution: ~80% ACTIVE, ~8% CONFIRMED, ~5% DRAFT, ~5% PAUSED, ~2% CLOSED
                mod = i % 100
                if mod < 80:
                    status_choice = SubscriptionStatus.ACTIVE
                elif mod < 88:
                    status_choice = SubscriptionStatus.CONFIRMED
                elif mod < 93:
                    status_choice = SubscriptionStatus.DRAFT
                elif mod < 98:
                    status_choice = SubscriptionStatus.PAUSED
                else:
                    status_choice = SubscriptionStatus.CLOSED

                start_d = today - timedelta(days=(i % 365))
                if status_choice == SubscriptionStatus.ACTIVE:
                    if i % 7 == 0:
                        next_d = today
                    else:
                        next_d = today + timedelta(days=1 + (i % 28))
                else:
                    next_d = None

                subs_to_create.append(
                    Subscription(
                        subscription_number=f"SUB-2026-{idx:05d}",
                        customer=customer,
                        plan=plan,
                        status=status_choice,
                        start_date=start_d,
                        next_billing_date=next_d,
                        payment_terms_days=30
                    )
                )

            Subscription.objects.bulk_create(subs_to_create, batch_size=1000)

            # Re-query new subscriptions to obtain IDs
            newly_created_subs = list(
                Subscription.objects.order_by('-id')[:subs_needed]
            )

            # Create lines for each subscription
            sub_lines_to_create = []
            for s in newly_created_subs:
                prod = products_list[s.id % len(products_list)]
                qty = (s.id % 3) + 1
                sub_lines_to_create.append(
                    SubscriptionLine(
                        subscription=s,
                        product=prod,
                        quantity=qty,
                        unit_price=prod.sales_price,
                        tax_rule=vat20
                    )
                )
            SubscriptionLine.objects.bulk_create(sub_lines_to_create, batch_size=1000)

        # 7. Invoices, Lines, and Payments
        self.stdout.write("Generating invoices with payments, open balances, and overdue records...")
        current_inv_count = Invoice.objects.count()
        target_inv_count = 2000
        invs_needed = max(0, target_inv_count - current_inv_count)

        if invs_needed > 0:
            all_subs = list(Subscription.objects.select_related('customer')[:invs_needed])
            invoices_to_create = []

            for i in range(invs_needed):
                idx = current_inv_count + i + 1
                sub = all_subs[i % len(all_subs)]
                customer = sub.customer

                # Distribution:
                # ~50% PAID (completed)
                # ~20% CONFIRMED overdue (due_date < today)
                # ~15% CONFIRMED open (due_date >= today)
                # ~10% DRAFT
                # ~5% CANCELLED
                mod = i % 100
                if mod < 50:
                    inv_status = InvoiceStatus.PAID
                    issue_d = today - timedelta(days=60 + (i % 90))
                    due_d = issue_d + timedelta(days=30)  # already past
                elif mod < 70:
                    inv_status = InvoiceStatus.CONFIRMED
                    issue_d = today - timedelta(days=40 + (i % 30))
                    due_d = issue_d + timedelta(days=15)  # due_d < today -> OVERDUE!
                elif mod < 85:
                    inv_status = InvoiceStatus.CONFIRMED
                    issue_d = today - timedelta(days=(i % 10))
                    due_d = today + timedelta(days=15 + (i % 20))  # due_d >= today -> Open current
                elif mod < 95:
                    inv_status = InvoiceStatus.DRAFT
                    issue_d = today - timedelta(days=(i % 5))
                    due_d = today + timedelta(days=30)
                else:
                    inv_status = InvoiceStatus.CANCELLED
                    issue_d = today - timedelta(days=30)
                    due_d = today

                subtotal = Decimal('100.00') + Decimal(f"{(i % 5) * 50}.00")
                tax_amt = (subtotal * Decimal('0.20')).quantize(Decimal('0.01'))
                total = subtotal + tax_amt

                invoices_to_create.append(
                    Invoice(
                        invoice_number=f"INV-2026-{idx:05d}",
                        subscription=sub,
                        customer=customer,
                        status=inv_status,
                        issue_date=issue_d,
                        due_date=due_d,
                        billing_period_start=issue_d,
                        billing_period_end=issue_d + timedelta(days=30),
                        subtotal=subtotal,
                        tax_amount=tax_amt,
                        discount_amount=Decimal('0.00'),
                        total_amount=total,
                    )
                )

            Invoice.objects.bulk_create(invoices_to_create, batch_size=1000)

            newly_created_invoices = list(
                Invoice.objects.order_by('-id')[:invs_needed]
            )

            # Invoice lines
            inv_lines_to_create = []
            for inv in newly_created_invoices:
                inv_lines_to_create.append(
                    InvoiceLine(
                        invoice=inv,
                        product=p1,
                        description=p1.name,
                        quantity=1,
                        unit_price=inv.subtotal,
                        tax_rate=Decimal('20.00'),
                        tax_amount=inv.tax_amount,
                        subtotal=inv.subtotal,
                        total=inv.total_amount
                    )
                )
            InvoiceLine.objects.bulk_create(inv_lines_to_create, batch_size=1000)

            # Payments
            payments_to_create = []
            for inv in newly_created_invoices:
                if inv.status == InvoiceStatus.PAID:
                    # 100% full settlement
                    p_date = timezone.make_aware(datetime.combine(inv.issue_date + timedelta(days=5), datetime.min.time()))
                    payments_to_create.append(
                        Payment(
                            invoice=inv,
                            amount=inv.total_amount,
                            payment_date=p_date,
                            method=PaymentMethod.BANK_TRANSFER,
                            transaction_reference=f"TXN-FULL-{inv.id}"
                        )
                    )
                elif inv.status == InvoiceStatus.CONFIRMED and inv.due_date < today:
                    # Partial payment on some overdue invoices (e.g. 50% paid)
                    if inv.id % 2 == 0:
                        part_amt = (inv.total_amount * Decimal('0.50')).quantize(Decimal('0.01'))
                        p_date = timezone.make_aware(datetime.combine(inv.issue_date + timedelta(days=5), datetime.min.time()))
                        payments_to_create.append(
                            Payment(
                                invoice=inv,
                                amount=part_amt,
                                payment_date=p_date,
                                method=PaymentMethod.CREDIT_CARD,
                                transaction_reference=f"TXN-PART-{inv.id}"
                            )
                        )

            Payment.objects.bulk_create(payments_to_create, batch_size=1000)

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded demo database in {elapsed:.2f}s!\n"
            f" - Total Customers:     {User.objects.filter(role=UserRole.CUSTOMER).count()}\n"
            f" - Total Products:      {Product.objects.count()}\n"
            f" - Total Plans:         {Plan.objects.count()}\n"
            f" - Total Subscriptions: {Subscription.objects.count()}\n"
            f" - Total Invoices:      {Invoice.objects.count()}\n"
            f" - Total Payments:      {Payment.objects.count()}\n"
            f" - Active Subs:         {Subscription.objects.filter(status=SubscriptionStatus.ACTIVE).count()}\n"
            f" - Overdue Invoices:    {Invoice.objects.filter(status=InvoiceStatus.CONFIRMED, due_date__lt=today).count()}\n"
            f"Demo Accounts:\n"
            f" - Admin:    admin@brightloop.io    / Password123!\n"
            f" - Staff:    staff@brightloop.io    / Password123!\n"
            f" - Customer: customer@brightloop.io / Password123!\n"
            f" - Customer: customer1@demo.com ... customer50@demo.com / Password123!"
        ))
