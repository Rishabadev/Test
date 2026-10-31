"""
core/utils.py - Reusable utilities for number generation, billing cycle calculations,
and lightweight PDF rendering.
"""

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.models import BillingPeriod, Invoice, Subscription


def advance_date_by_period(start_date: date, period: str) -> date:
    """
    Computes the next billing date given a start date and billing period interval.
    Handles month-end boundary cases (e.g. Jan 31 -> Feb 28).
    """
    if period == BillingPeriod.DAILY:
        return start_date + timedelta(days=1)
    elif period == BillingPeriod.WEEKLY:
        return start_date + timedelta(weeks=1)
    elif period == BillingPeriod.MONTHLY:
        year = start_date.year + (start_date.month // 12)
        month = (start_date.month % 12) + 1
        day = min(start_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    elif period == BillingPeriod.YEARLY:
        year = start_date.year + 1
        day = min(start_date.day, calendar.monthrange(year, start_date.month)[1])
        return date(year, start_date.month, day)
    return start_date + timedelta(days=30)


def generate_subscription_number(date_val=None) -> str:
    """
    Generates a unique subscription number in format: SUB-YYYY-XXXX (e.g. SUB-2026-0001).
    """
    if isinstance(date_val, str):
        parsed = parse_date(date_val)
        target_date = parsed if parsed else timezone.localdate()
    elif hasattr(date_val, 'year'):
        target_date = date_val
    else:
        target_date = timezone.localdate()

    year = target_date.year
    prefix = f"SUB-{year}-"

    existing_numbers = Subscription.objects.filter(
        subscription_number__startswith=prefix
    ).values_list('subscription_number', flat=True)

    max_seq = 0
    pattern = re.compile(rf"^SUB-{year}-(\d+)$")
    for num_str in existing_numbers:
        match = pattern.match(num_str)
        if match:
            try:
                val = int(match.group(1))
                if val > max_seq:
                    max_seq = val
            except ValueError:
                pass

    next_seq = max_seq + 1
    candidate = f"{prefix}{next_seq:04d}"
    while Subscription.objects.filter(subscription_number=candidate).exists():
        next_seq += 1
        candidate = f"{prefix}{next_seq:04d}"

    return candidate


def generate_invoice_number(issue_date=None) -> str:
    """
    Generates a unique invoice number in format: INV-YYYY-XXXX (e.g. INV-2026-0001).
    """
    if isinstance(issue_date, str):
        parsed = parse_date(issue_date)
        target_date = parsed if parsed else timezone.localdate()
    elif hasattr(issue_date, 'year'):
        target_date = issue_date
    else:
        target_date = timezone.localdate()

    year = target_date.year
    prefix = f"INV-{year}-"

    existing_numbers = Invoice.objects.filter(
        invoice_number__startswith=prefix
    ).values_list('invoice_number', flat=True)

    max_seq = 0
    pattern = re.compile(rf"^INV-{year}-(\d+)$")
    for num_str in existing_numbers:
        match = pattern.match(num_str)
        if match:
            try:
                val = int(match.group(1))
                if val > max_seq:
                    max_seq = val
            except ValueError:
                pass

    next_seq = max_seq + 1
    candidate = f"{prefix}{next_seq:04d}"
    while Invoice.objects.filter(invoice_number=candidate).exists():
        next_seq += 1
        candidate = f"{prefix}{next_seq:04d}"

    return candidate


def build_simple_pdf(text_lines: list[str]) -> bytes:
    """
    Generates a valid, well-formed PDF 1.4 byte document in pure Python.
    No external heavy binary dependencies required.
    """
    stream_lines = ['BT', '/F1 11 Tf', '14 TL', '50 750 Td']
    for line in text_lines:
        safe_line = (
            str(line)
            .replace('\\', '\\\\')
            .replace('(', '\\(')
            .replace(')', '\\)')
        )
        stream_lines.append(f'({safe_line}) Tj')
        stream_lines.append('T*')
    stream_lines.append('ET')
    stream_data = '\n'.join(stream_lines).encode('latin1', errors='replace')

    objects = []
    objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    objects.append(
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n'
    )
    objects.append(b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')

    obj5 = (
        b'5 0 obj\n<< /Length '
        + str(len(stream_data)).encode('ascii')
        + b' >>\nstream\n'
        + stream_data
        + b'\nendstream\nendobj\n'
    )
    objects.append(obj5)

    header = b'%PDF-1.4\n'
    offsets = []
    current_offset = len(header)
    for obj in objects:
        offsets.append(current_offset)
        current_offset += len(obj)

    xref = b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets:
        xref += f'{off:010d} 00000 n \n'.encode('ascii')

    trailer = (
        b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'
        + str(current_offset).encode('ascii')
        + b'\n%%EOF\n'
    )

    return header + b''.join(objects) + xref + trailer


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Renders an Invoice instance to a structured PDF document.
    """
    lines = [
        "============================================================",
        "                  BRIGHTLOOP SOFTWARE INC.                  ",
        "                         INVOICE                            ",
        "============================================================",
        f"Invoice Number:        {invoice.invoice_number}",
        f"Status:                {invoice.status}",
        f"Issue Date:            {invoice.issue_date}",
        f"Due Date:              {invoice.due_date}",
        f"Customer:              {invoice.customer.email}",
        f"Subscription:          {invoice.subscription.subscription_number if invoice.subscription else 'N/A'}",
        f"Billing Period:        {invoice.billing_period_start} to {invoice.billing_period_end}",
        "------------------------------------------------------------",
        "LINE ITEMS:",
    ]

    for item in invoice.lines.all():
        desc = item.description[:35]
        lines.append(
            f"  * {desc:<35} | Qty: {item.quantity:>2} | Price: ${item.unit_price:>8} | Tax: ${item.tax_amount:>6} | Total: ${item.total:>8}"
        )

    lines.extend([
        "------------------------------------------------------------",
        f"Subtotal:              ${invoice.subtotal:>10}",
        f"Tax Amount:            ${invoice.tax_amount:>10}",
        f"Discount Amount:      -${invoice.discount_amount:>10}",
        f"TOTAL AMOUNT:          ${invoice.total_amount:>10}",
        "------------------------------------------------------------",
        f"Amount Paid:           ${invoice.amount_paid:>10}",
        f"Amount Due:            ${invoice.amount_due:>10}",
        "============================================================",
        "Thank you for choosing Brightloop Software!",
        "For billing inquiries, contact billing@brightloop.io",
    ])

    return build_simple_pdf(lines)

