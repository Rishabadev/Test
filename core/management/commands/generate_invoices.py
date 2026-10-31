"""
core/management/commands/generate_invoices.py - Automated recurring invoice generation.

Pricing rule: Invoice lines are copied from SubscriptionLines only. Plan.price is not billed separately.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.models import (
    Discount,
    DiscountType,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Subscription,
    SubscriptionStatus,
)
from core.utils import advance_date_by_period, generate_invoice_number


class Command(BaseCommand):
    help = "Generates recurring billing invoices for active subscriptions."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Reference execution date (YYYY-MM-DD). Defaults to today.',
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            today = parse_date(date_str)
            if not today:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {date_str}. Expected YYYY-MM-DD."))
                return
        else:
            today = timezone.localdate()

        self.stdout.write(f"Starting recurring invoice generation for date: {today}")

        # 1. Select ACTIVE subscriptions where next_billing_date <= today (skip PAUSED/CLOSED)
        eligible_sub_ids = list(
            Subscription.objects.filter(
                status=SubscriptionStatus.ACTIVE,
                next_billing_date__lte=today
            ).values_list('id', flat=True)
        )

        created_count = 0
        skipped_count = 0
        errors_count = 0

        for sub_id in eligible_sub_ids:
            try:
                with transaction.atomic():
                    # Row-level lock on the subscription (avoid outer joins with select_for_update in Postgres)
                    locked_sub = (
                        Subscription.objects.select_for_update()
                        .select_related('plan', 'customer')
                        .get(pk=sub_id)
                    )

                    # Re-verify status under row lock
                    if locked_sub.status != SubscriptionStatus.ACTIVE:
                        skipped_count += 1
                        continue

                    if not locked_sub.next_billing_date or locked_sub.next_billing_date > today:
                        skipped_count += 1
                        continue

                    # 2. Compute billing period from plan.billing_period
                    billing_period_start = locked_sub.next_billing_date
                    billing_period_end = advance_date_by_period(
                        billing_period_start,
                        locked_sub.plan.billing_period
                    )

                    # Idempotency pre-check
                    if Invoice.objects.filter(
                        subscription=locked_sub,
                        billing_period_start=billing_period_start,
                        billing_period_end=billing_period_end
                    ).exclude(status=InvoiceStatus.CANCELLED).exists():
                        skipped_count += 1
                        continue

                    # 3. Snapshot lines from SubscriptionLines only
                    sub_lines = list(locked_sub.lines.all())
                    invoice_lines_to_create = []
                    total_subtotal = Decimal('0.00')
                    total_tax = Decimal('0.00')
                    total_quantity = 0

                    for s_line in sub_lines:
                        qty = s_line.quantity
                        unit_p = s_line.unit_price
                        line_subtotal = (Decimal(qty) * Decimal(unit_p)).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )

                        tax_rate = s_line.tax_rule.rate if s_line.tax_rule else Decimal('0.00')
                        line_tax = ((line_subtotal * tax_rate) / Decimal('100.00')).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                        line_total = line_subtotal + line_tax

                        if s_line.variant:
                            desc = f"{s_line.product.name} ({s_line.variant.attribute_name}: {s_line.variant.attribute_value})"
                        else:
                            desc = s_line.product.name

                        invoice_lines_to_create.append(
                            InvoiceLine(
                                product=s_line.product,
                                description=desc,
                                quantity=qty,
                                unit_price=unit_p,
                                tax_rate=tax_rate,
                                tax_amount=line_tax,
                                subtotal=line_subtotal,
                                total=line_total,
                            )
                        )

                        total_subtotal += line_subtotal
                        total_tax += line_tax
                        total_quantity += qty

                    # 4. Apply discount logic
                    discount_to_apply = None
                    discount_amount = Decimal('0.00')
                    discount = locked_sub.discount

                    if discount:
                        covered_products = list(discount.products.all())
                        if len(covered_products) == 0:
                            # Empty products = whole subscription
                            eligible_lines = invoice_lines_to_create
                        else:
                            covered_ids = {p.id for p in covered_products}
                            eligible_lines = [
                                l for l in invoice_lines_to_create if l.product_id in covered_ids
                            ]

                        eligible_subtotal = sum(l.subtotal for l in eligible_lines)
                        eligible_qty = sum(l.quantity for l in eligible_lines)

                        meets_min_amount = (
                            total_subtotal >= discount.min_purchase_amount
                            or eligible_subtotal >= discount.min_purchase_amount
                        )
                        meets_min_qty = (
                            total_quantity >= discount.min_quantity
                            or eligible_qty >= discount.min_quantity
                        )

                        if (
                            discount.is_valid_now()
                            and meets_min_amount
                            and meets_min_qty
                            and len(eligible_lines) > 0
                        ):
                            if discount.discount_type == DiscountType.PERCENTAGE:
                                discount_calc = (eligible_subtotal * discount.value) / Decimal('100.00')
                                discount_amount = discount_calc.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            elif discount.discount_type == DiscountType.FIXED:
                                discount_amount = min(discount.value, eligible_subtotal)

                            discount_to_apply = discount
                            # Increment current_uses with F() expression in the same transaction
                            Discount.objects.filter(pk=discount.pk).update(current_uses=F('current_uses') + 1)

                    total_amount = max(Decimal('0.00'), total_subtotal + total_tax - discount_amount)

                    # 5. Create Invoice & lines
                    inv_number = generate_invoice_number(issue_date=today)
                    due_date = today + timedelta(days=locked_sub.payment_terms_days)

                    invoice = Invoice.objects.create(
                        invoice_number=inv_number,
                        subscription=locked_sub,
                        customer=locked_sub.customer,
                        discount=discount_to_apply,
                        status=InvoiceStatus.DRAFT,
                        issue_date=today,
                        due_date=due_date,
                        billing_period_start=billing_period_start,
                        billing_period_end=billing_period_end,
                        subtotal=total_subtotal,
                        tax_amount=total_tax,
                        discount_amount=discount_amount,
                        total_amount=total_amount,
                    )

                    for inv_line in invoice_lines_to_create:
                        inv_line.invoice = invoice
                    InvoiceLine.objects.bulk_create(invoice_lines_to_create)

                    # 6. Advance next_billing_date by one period
                    locked_sub.next_billing_date = billing_period_end

                    # Auto-close check: past expiry_date if plan.auto_close_at_end
                    if (
                        locked_sub.plan.auto_close_at_end
                        and locked_sub.expiry_date
                        and (locked_sub.expiry_date <= today or locked_sub.next_billing_date > locked_sub.expiry_date)
                    ):
                        locked_sub.status = SubscriptionStatus.CLOSED
                        locked_sub.save(update_fields=['next_billing_date', 'status', 'updated_at'])
                    else:
                        locked_sub.save(update_fields=['next_billing_date', 'updated_at'])

                    created_count += 1

            except IntegrityError:
                # Idempotency guarantee: unique constraint on (subscription, billing_period_start, billing_period_end)
                skipped_count += 1
                continue
            except Exception as exc:
                errors_count += 1
                self.stderr.write(f"Error billing subscription {sub_id}: {exc}")
                continue

        summary = f"created={created_count}, skipped={skipped_count}, errors={errors_count}"
        self.stdout.write(f"Invoice generation finished: {summary}")
        return summary
