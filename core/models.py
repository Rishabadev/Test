from django.db import models
"""
core/models.py - Unified models for Brightloop Software Subscription Management.
Includes Custom User, Catalog, Subscriptions, Invoicing, and Payments.
"""

from decimal import Decimal
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone


# ==========================================
# 1. USER & AUTHENTICATION
# ==========================================

class CustomUserManager(BaseUserManager):
    """Manager for custom user where email is the unique identifier for auth."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrator'
    STAFF = 'STAFF', 'Internal Staff'
    CUSTOMER = 'CUSTOMER', 'Customer'


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        app_label = 'core'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if self.role == UserRole.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)


# ==========================================
# 2. CATALOG: PRODUCTS, VARIANTS, PLANS, TAXES, DISCOUNTS
# ==========================================

class TaxRule(models.Model):
    name = models.CharField(max_length=100)
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage rate, e.g. 18.00 for 18%",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class ProductType(models.TextChoices):
    SERVICE = 'SERVICE', 'Service'
    SOFTWARE = 'SOFTWARE', 'Software License'
    HARDWARE = 'HARDWARE', 'Hardware'
    CONSUMABLE = 'CONSUMABLE', 'Consumable'


class Product(models.Model):
    name = models.CharField(max_length=255)
    product_type = models.CharField(
        max_length=50,
        choices=ProductType.choices,
        default=ProductType.SOFTWARE
    )
    sales_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    attribute_name = models.CharField(max_length=100)
    attribute_value = models.CharField(max_length=100)
    price_extra = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount added to product base sales price"
    )

    class Meta:
        app_label = 'core'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'attribute_name', 'attribute_value'],
                name='unique_product_variant'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.attribute_name}:{self.attribute_value} (+{self.price_extra})"


class BillingPeriod(models.TextChoices):
    DAILY = 'DAILY', 'Daily'
    WEEKLY = 'WEEKLY', 'Weekly'
    MONTHLY = 'MONTHLY', 'Monthly'
    YEARLY = 'YEARLY', 'Yearly'


class Plan(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    billing_period = models.CharField(
        max_length=20,
        choices=BillingPeriod.choices,
        default=BillingPeriod.MONTHLY
    )
    min_quantity = models.PositiveIntegerField(default=1)
    available_from = models.DateField(default=timezone.localdate)
    available_to = models.DateField(null=True, blank=True)

    auto_close_at_end = models.BooleanField(
        default=False,
        help_text="If True, subscription automatically transitions to CLOSED on expiry date"
    )
    allow_early_close = models.BooleanField(
        default=True,
        help_text="If True, staff or customer can cancel before expiry date"
    )
    allow_pause = models.BooleanField(default=False)
    allow_renew = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'

    def clean(self):
        if self.available_to and self.available_from > self.available_to:
            raise ValidationError("available_to cannot be prior to available_from.")

    def __str__(self):
        return f"{self.name} ({self.get_billing_period_display()})"


class DiscountType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED = 'FIXED', 'Fixed Amount'


class Discount(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name='discounts',
        help_text="Leave empty to apply to the whole subscription"
    )
    min_purchase_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    min_quantity = models.PositiveIntegerField(default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for unlimited uses"
    )
    current_uses = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'

    def is_valid_now(self) -> bool:
        today = timezone.localdate()
        if not self.is_active:
            return False
        if not (self.start_date <= today <= self.end_date):
            return False
        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return False
        return True

    def __str__(self):
        return f"{self.code} ({self.value} {self.discount_type})"


# ==========================================
# 3. QUOTATION TEMPLATES
# ==========================================

class QuotationTemplate(models.Model):
    name = models.CharField(max_length=255)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    validity_days = models.PositiveIntegerField(
        default=30,
        help_text="Default number of days a quote using this template remains valid"
    )

    class Meta:
        app_label = 'core'

    def __str__(self):
        return self.name


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.template.name} - {self.product.name} x {self.quantity}"


# ==========================================
# 4. SUBSCRIPTIONS
# ==========================================

class SubscriptionStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    QUOTATION = 'QUOTATION', 'Quotation'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    CLOSED = 'CLOSED', 'Closed'


class Subscription(models.Model):
    subscription_number = models.CharField(max_length=64, unique=True, db_index=True)
    customer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        limit_choices_to={'role': UserRole.CUSTOMER}
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    discount = models.ForeignKey(Discount, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.DRAFT,
        db_index=True
    )
    start_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(
        null=True,
        blank=True,
        help_text="Scheduled date for the next recurring invoice generation"
    )
    payment_terms_days = models.PositiveIntegerField(
        default=30,
        help_text="Due date offset from invoice issue date in days (e.g. Net 30)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'expiry_date']),
            models.Index(fields=['status', 'next_billing_date']),
        ]

    def __str__(self):
        return f"{self.subscription_number} - {self.customer.email} [{self.status}]"

    def can_transition_to(self, new_status: str) -> bool:
        """
        Validates state machine flow:
        DRAFT -> QUOTATION -> CONFIRMED -> ACTIVE <-> PAUSED
        Any pre-terminal state can transition to CLOSED.
        """
        valid_transitions = {
            SubscriptionStatus.DRAFT: [SubscriptionStatus.QUOTATION, SubscriptionStatus.CLOSED],
            SubscriptionStatus.QUOTATION: [SubscriptionStatus.CONFIRMED, SubscriptionStatus.CLOSED],
            SubscriptionStatus.CONFIRMED: [SubscriptionStatus.ACTIVE, SubscriptionStatus.CLOSED],
            SubscriptionStatus.ACTIVE: [SubscriptionStatus.PAUSED, SubscriptionStatus.CLOSED],
            SubscriptionStatus.PAUSED: [SubscriptionStatus.ACTIVE, SubscriptionStatus.CLOSED],
            SubscriptionStatus.CLOSED: []  # Terminal state
        }
        return new_status in valid_transitions.get(self.status, [])

    def transition_to(self, new_status: str):
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rule = models.ForeignKey(TaxRule, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        app_label = 'core'

    @property
    def subtotal(self) -> Decimal:
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.subscription.subscription_number} - {self.product.name} (x{self.quantity})"


# ==========================================
# 5. INVOICING & BILLING ENGINE
# ==========================================

class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    PAID = 'PAID', 'Paid'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices'
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    discount = models.ForeignKey(
        Discount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices',
        help_text="Snapshot of discount code applied to this invoice"
    )
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True
    )
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()

    # Billing period idempotency windows
    billing_period_start = models.DateField(
        help_text="Start date of service cycle covered by this invoice"
    )
    billing_period_end = models.DateField(
        help_text="End date of service cycle covered by this invoice"
    )

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        constraints = [
            # IDEMPOTENCY GUARANTEE:
            # Prevents billing the same subscription for the same start and end dates twice,
            # unless the previous invoice was officially CANCELLED.
            models.UniqueConstraint(
                fields=['subscription', 'billing_period_start', 'billing_period_end'],
                condition=~Q(status=InvoiceStatus.CANCELLED) & Q(subscription__isnull=False),
                name='unique_subscription_billing_period'
            )
        ]
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['subscription', 'billing_period_start', 'billing_period_end']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.email} (${self.total_amount})"

    def can_transition_to(self, new_status: str) -> bool:
        """
        Validates invoice lifecycle transitions:
        DRAFT -> CONFIRMED -> PAID
        DRAFT/CONFIRMED -> CANCELLED
        """
        valid_transitions = {
            InvoiceStatus.DRAFT: [InvoiceStatus.CONFIRMED, InvoiceStatus.CANCELLED],
            InvoiceStatus.CONFIRMED: [InvoiceStatus.PAID, InvoiceStatus.CANCELLED],
            InvoiceStatus.PAID: [],       # Terminal state
            InvoiceStatus.CANCELLED: []   # Terminal state
        }
        return new_status in valid_transitions.get(self.status, [])

    def transition_to(self, new_status: str):
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

    @property
    def amount_paid(self) -> Decimal:
        aggregate = self.payments.aggregate(total=Sum('amount'))['total']
        return aggregate or Decimal('0.00')

    @property
    def amount_due(self) -> Decimal:
        return max(Decimal('0.00'), self.total_amount - self.amount_paid)

    @property
    def is_overdue(self) -> bool:
        if self.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
            return False
        return self.due_date < timezone.localdate() and self.amount_due > Decimal('0.00')


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Snapshot of the tax percentage rate applied"
    )
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description} (${self.total})"


# ==========================================
# 6. PAYMENTS
# ==========================================

class PaymentMethod(models.TextChoices):
    CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
    CASH = 'CASH', 'Cash'
    OTHER = 'OTHER', 'Other'

class Payment(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateTimeField(default=timezone.now, db_index=True)
    method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER
    )
    transaction_reference = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['invoice', 'payment_date']),
        ]

    def __str__(self):
        return f"Payment {self.id} for {self.invoice.invoice_number}: ${self.amount}"

    def clean(self):
        super().clean()
        if self.invoice_id and self.invoice.status != InvoiceStatus.CONFIRMED:
            raise ValidationError(
                f"Payments can only be logged against CONFIRMED invoices. Current status is {self.invoice.status}."
            )

    def save(self, *args, **kwargs):
        """
        Concurrency-safe, append-only payment recording with row-level locking.
        Payments are immutable once saved; attempts to edit an existing instance
        raise a ValidationError. Transitions the parent invoice to PAID when settled.
        """
        if self.pk:
            raise ValidationError("Payments cannot be edited. Record a correcting entry instead.")

        self.full_clean()

        with transaction.atomic():
            # Acquire row lock on the invoice to eliminate race conditions
            locked_invoice = Invoice.objects.select_for_update().get(pk=self.invoice_id)

            if locked_invoice.status != InvoiceStatus.CONFIRMED:
                raise ValidationError(
                    f"Payments can only be logged against CONFIRMED invoices. Current status is {locked_invoice.status}."
                )

            prior_payments_sum = (
                locked_invoice.payments.aggregate(total=Sum('amount'))['total']
                or Decimal('0.00')
            )
            outstanding_balance = locked_invoice.total_amount - prior_payments_sum

            if self.amount > outstanding_balance:
                raise ValidationError(
                    f"Payment amount (${self.amount}) exceeds outstanding invoice balance (${outstanding_balance})."
                )

            super().save(*args, **kwargs)

            # Check if invoice is fully settled
            if prior_payments_sum + self.amount >= locked_invoice.total_amount:
                locked_invoice.transition_to(InvoiceStatus.PAID)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payments cannot be deleted. Record a correcting entry instead.")