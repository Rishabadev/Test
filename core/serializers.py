"""
core/serializers.py - Auth serializers for Signup, Resets, and Staff creation.
Catalog, Quotation Templates, Subscription, Invoicing, and Payment serializers.
"""

import re
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.models import (
    UserRole,
    TaxRule,
    Product,
    ProductVariant,
    Plan,
    Discount,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
    SubscriptionStatus,
    ProductType,
    BillingPeriod,
    DiscountType,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)

User = get_user_model()


# ==========================================
# 1. AUTHENTICATION SERIALIZERS
# ==========================================

class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="An account with this email address already exists."
            )
        ]
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name')

    def validate_password(self, value):
        # Executes all checks registered in AUTH_PASSWORD_VALIDATORS
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        # Hardcode CUSTOMER role; prevents privilege escalation from browser requests
        user = User(
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=UserRole.CUSTOMER,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def validate_email(self, value):
        return value.strip().lower()


class StaffUserCreateSerializer(serializers.ModelSerializer):
    """Exclusively used by Admins to provision internal Staff accounts."""
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with this email address already exists."
            )
        ]
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name')

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        user = User(
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=UserRole.STAFF,
            is_staff=False,  # Internal staff role; only Admins receive Django Admin portal access
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uidb64']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "The reset link is invalid or has expired."})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "The reset link is invalid or has expired."})

        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class CurrentUserSerializer(serializers.ModelSerializer):
    """Used for GET /api/auth/me/ to inspect currently logged-in user profile."""
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role')
        read_only_fields = fields


# ==========================================
# 2. NUMBER GENERATION HELPER
# ==========================================

def generate_subscription_number(date=None) -> str:
    """
    Generates a unique subscription number in format: SUB-YYYY-XXXX (e.g. SUB-2026-0001).
    """
    from core.utils import generate_subscription_number as gen_sub
    return gen_sub(date)


# ==========================================
# 3. CATALOG SERIALIZERS
# ==========================================

class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = ('id', 'name', 'rate', 'is_active')


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ('id', 'product', 'attribute_name', 'attribute_value', 'price_extra')


class ProductVariantInlineSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = ProductVariant
        fields = ('id', 'attribute_name', 'attribute_value', 'price_extra')


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantInlineSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'product_type', 'sales_price',
            'cost_price', 'notes', 'is_active', 'variants'
        )

    def create(self, validated_data):
        variants_data = validated_data.pop('variants', [])
        product = Product.objects.create(**validated_data)
        for variant_data in variants_data:
            ProductVariant.objects.create(product=product, **variant_data)
        return product

    def update(self, instance, validated_data):
        variants_data = validated_data.pop('variants', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if variants_data is not None:
            keep_variant_ids = []
            for v_data in variants_data:
                v_id = v_data.get('id')
                if v_id and ProductVariant.objects.filter(id=v_id, product=instance).exists():
                    variant = ProductVariant.objects.get(id=v_id, product=instance)
                    variant.attribute_name = v_data.get('attribute_name', variant.attribute_name)
                    variant.attribute_value = v_data.get('attribute_value', variant.attribute_value)
                    variant.price_extra = v_data.get('price_extra', variant.price_extra)
                    variant.save()
                    keep_variant_ids.append(variant.id)
                else:
                    new_variant = ProductVariant.objects.create(
                        product=instance,
                        attribute_name=v_data.get('attribute_name'),
                        attribute_value=v_data.get('attribute_value'),
                        price_extra=v_data.get('price_extra', Decimal('0.00'))
                    )
                    keep_variant_ids.append(new_variant.id)
            instance.variants.exclude(id__in=keep_variant_ids).delete()

        return instance


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            'id', 'name', 'price', 'billing_period', 'min_quantity',
            'available_from', 'available_to', 'auto_close_at_end',
            'allow_early_close', 'allow_pause', 'allow_renew'
        )

    def validate(self, attrs):
        available_from = attrs.get('available_from') or (self.instance.available_from if self.instance else timezone.localdate())
        available_to = attrs.get('available_to', getattr(self.instance, 'available_to', None))
        if available_to and available_from > available_to:
            raise serializers.ValidationError({"available_to": "available_to cannot be prior to available_from."})
        return attrs


class DiscountSerializer(serializers.ModelSerializer):
    is_valid_now = serializers.BooleanField(read_only=True)
    products = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Product.objects.all(),
        required=False
    )

    class Meta:
        model = Discount
        fields = (
            'id', 'code', 'discount_type', 'value', 'products',
            'min_purchase_amount', 'min_quantity', 'start_date', 'end_date',
            'max_uses', 'current_uses', 'is_active', 'is_valid_now'
        )
        read_only_fields = ('current_uses',)

    def validate(self, attrs):
        start_date = attrs.get('start_date') or (self.instance.start_date if self.instance else None)
        end_date = attrs.get('end_date') or (self.instance.end_date if self.instance else None)
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "end_date cannot be prior to start_date."})
        return attrs


# ==========================================
# 4. QUOTATION TEMPLATE SERIALIZERS
# ==========================================

class QuotationTemplateLineNestedSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.SerializerMethodField(read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    class Meta:
        model = QuotationTemplateLine
        fields = (
            'id', 'product', 'product_name', 'variant', 'variant_name',
            'quantity', 'unit_price'
        )

    def get_variant_name(self, obj):
        if obj.variant:
            return f"{obj.variant.attribute_name}: {obj.variant.attribute_value}"
        return None

    def validate(self, attrs):
        product = attrs.get('product') or (self.instance.product if self.instance else None)
        variant = attrs.get('variant', getattr(self.instance, 'variant', None))
        if not product:
            raise serializers.ValidationError({"product": "Product is required."})
        if variant and variant.product_id != product.id:
            raise serializers.ValidationError({"variant": "Variant does not belong to the selected product."})

        # Calculate unit_price if omitted
        if 'unit_price' not in attrs or attrs['unit_price'] is None:
            price_extra = variant.price_extra if variant else Decimal('0.00')
            attrs['unit_price'] = product.sales_price + price_extra
        return attrs


class QuotationTemplateLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.SerializerMethodField(read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    class Meta:
        model = QuotationTemplateLine
        fields = (
            'id', 'template', 'product', 'product_name', 'variant',
            'variant_name', 'quantity', 'unit_price'
        )

    def get_variant_name(self, obj):
        if obj.variant:
            return f"{obj.variant.attribute_name}: {obj.variant.attribute_value}"
        return None

    def validate(self, attrs):
        product = attrs.get('product') or (self.instance.product if self.instance else None)
        variant = attrs.get('variant', getattr(self.instance, 'variant', None))
        if not product:
            raise serializers.ValidationError({"product": "Product is required."})
        if variant and variant.product_id != product.id:
            raise serializers.ValidationError({"variant": "Variant does not belong to the selected product."})

        # Calculate unit_price if omitted: base price + variant price extra
        if 'unit_price' not in attrs or attrs['unit_price'] is None:
            price_extra = variant.price_extra if variant else Decimal('0.00')
            attrs['unit_price'] = product.sales_price + price_extra
        return attrs


class QuotationTemplateSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    lines = QuotationTemplateLineNestedSerializer(many=True, required=False)

    class Meta:
        model = QuotationTemplate
        fields = ('id', 'name', 'plan', 'plan_name', 'validity_days', 'lines')

    def create(self, validated_data):
        lines_data = validated_data.pop('lines', [])
        template = QuotationTemplate.objects.create(**validated_data)
        for line_data in lines_data:
            line_data.pop('id', None)
            product = line_data['product']
            variant = line_data.get('variant')
            unit_price = line_data.get('unit_price')
            if unit_price is None:
                price_extra = variant.price_extra if variant else Decimal('0.00')
                unit_price = product.sales_price + price_extra
            QuotationTemplateLine.objects.create(
                template=template,
                product=product,
                variant=variant,
                quantity=line_data.get('quantity', 1),
                unit_price=unit_price
            )
        return template

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data.pop('id', None)
                product = line_data['product']
                variant = line_data.get('variant')
                unit_price = line_data.get('unit_price')
                if unit_price is None:
                    price_extra = variant.price_extra if variant else Decimal('0.00')
                    unit_price = product.sales_price + price_extra
                QuotationTemplateLine.objects.create(
                    template=instance,
                    product=product,
                    variant=variant,
                    quantity=line_data.get('quantity', 1),
                    unit_price=unit_price
                )
        return instance


# ==========================================
# 5. SUBSCRIPTION SERIALIZERS
# ==========================================

class SubscriptionLineNestedSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.SerializerMethodField(read_only=True)
    tax_rate = serializers.DecimalField(
        source='tax_rule.rate',
        max_digits=5,
        decimal_places=2,
        read_only=True,
        allow_null=True
    )
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    class Meta:
        model = SubscriptionLine
        fields = (
            'id', 'product', 'product_name', 'variant', 'variant_name',
            'quantity', 'unit_price', 'tax_rule', 'tax_rate', 'subtotal'
        )

    def get_variant_name(self, obj):
        if obj.variant:
            return f"{obj.variant.attribute_name}: {obj.variant.attribute_value}"
        return None

    def validate(self, attrs):
        product = attrs.get('product') or (self.instance.product if self.instance else None)
        variant = attrs.get('variant', getattr(self.instance, 'variant', None))
        if not product:
            raise serializers.ValidationError({"product": "Product is required."})
        if variant and variant.product_id != product.id:
            raise serializers.ValidationError({"variant": "Variant does not belong to the selected product."})

        # Enforce business rule: Unit price = product.sales_price + variant.price_extra
        price_extra = variant.price_extra if variant else Decimal('0.00')
        attrs['unit_price'] = product.sales_price + price_extra
        return attrs


class SubscriptionLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.SerializerMethodField(read_only=True)
    tax_rate = serializers.DecimalField(
        source='tax_rule.rate',
        max_digits=5,
        decimal_places=2,
        read_only=True,
        allow_null=True
    )
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    class Meta:
        model = SubscriptionLine
        fields = (
            'id', 'subscription', 'product', 'product_name', 'variant',
            'variant_name', 'quantity', 'unit_price', 'tax_rule', 'tax_rate', 'subtotal'
        )

    def get_variant_name(self, obj):
        if obj.variant:
            return f"{obj.variant.attribute_name}: {obj.variant.attribute_value}"
        return None

    def validate(self, attrs):
        product = attrs.get('product') or (self.instance.product if self.instance else None)
        variant = attrs.get('variant', getattr(self.instance, 'variant', None))
        if not product:
            raise serializers.ValidationError({"product": "Product is required."})
        if variant and variant.product_id != product.id:
            raise serializers.ValidationError({"variant": "Variant does not belong to the selected product."})

        # Enforce business rule: Unit price = product.sales_price + variant.price_extra
        price_extra = variant.price_extra if variant else Decimal('0.00')
        attrs['unit_price'] = product.sales_price + price_extra
        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(read_only=True)
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_billing_period = serializers.CharField(source='plan.billing_period', read_only=True)
    plan_price = serializers.DecimalField(source='plan.price', max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.SerializerMethodField(read_only=True)
    discount_code = serializers.CharField(source='discount.code', read_only=True, allow_null=True)
    lines = SubscriptionLineNestedSerializer(many=True, required=False)

    class Meta:
        model = Subscription
        fields = (
            'id', 'subscription_number', 'customer', 'customer_email',
            'plan', 'plan_name', 'plan_billing_period', 'plan_price', 'total_amount',
            'discount', 'discount_code', 'status',
            'start_date', 'expiry_date', 'next_billing_date',
            'payment_terms_days', 'lines', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'subscription_number', 'created_at', 'updated_at')

    def get_total_amount(self, obj):
        total = Decimal('0.00')
        for line in obj.lines.all():
            total += line.subtotal
        return total

    def validate_customer(self, value):
        if value.role != UserRole.CUSTOMER:
            raise serializers.ValidationError("Designated customer must have the CUSTOMER role.")
        return value

    def create(self, validated_data):
        from core.utils import generate_subscription_number
        lines_data = validated_data.pop('lines', [])

        if 'subscription_number' not in validated_data:
            validated_data['subscription_number'] = generate_subscription_number(
                validated_data.get('start_date')
            )

        status_val = validated_data.get('status', SubscriptionStatus.DRAFT)
        # When a subscription moves to ACTIVE, set next_billing_date = start_date
        if status_val == SubscriptionStatus.ACTIVE:
            validated_data['next_billing_date'] = validated_data.get('start_date', timezone.localdate())

        with transaction.atomic():
            subscription = Subscription.objects.create(**validated_data)
            for line_data in lines_data:
                line_data.pop('id', None)
                product = line_data['product']
                variant = line_data.get('variant')
                price_extra = variant.price_extra if variant else Decimal('0.00')
                unit_price = product.sales_price + price_extra
                SubscriptionLine.objects.create(
                    subscription=subscription,
                    product=product,
                    variant=variant,
                    quantity=line_data.get('quantity', 1),
                    unit_price=unit_price,
                    tax_rule=line_data.get('tax_rule')
                )
        return subscription

    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)
        new_status = validated_data.get('status')

        if new_status and new_status != instance.status:
            if not instance.can_transition_to(new_status):
                raise serializers.ValidationError(
                    {"status": f"Invalid status transition from {instance.status} to {new_status}."}
                )
            # When a subscription moves to ACTIVE, set next_billing_date = start_date
            if new_status == SubscriptionStatus.ACTIVE:
                instance.next_billing_date = validated_data.get('start_date', instance.start_date)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                line_data.pop('id', None)
                product = line_data['product']
                variant = line_data.get('variant')
                price_extra = variant.price_extra if variant else Decimal('0.00')
                unit_price = product.sales_price + price_extra
                SubscriptionLine.objects.create(
                    subscription=instance,
                    product=product,
                    variant=variant,
                    quantity=line_data.get('quantity', 1),
                    unit_price=unit_price,
                    tax_rule=line_data.get('tax_rule')
                )
        return instance


# ==========================================
# 6. INVOICING & PAYMENT SERIALIZERS
# ==========================================

class InvoiceLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, allow_null=True)

    class Meta:
        model = InvoiceLine
        fields = (
            'id', 'product', 'product_name', 'description', 'quantity',
            'unit_price', 'tax_rate', 'tax_amount', 'subtotal', 'total'
        )
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'invoice', 'invoice_number', 'amount', 'payment_date',
            'method', 'transaction_reference', 'note', 'created_at'
        )
        read_only_fields = ('id', 'payment_date', 'created_at')

    def validate(self, attrs):
        invoice = attrs.get('invoice')
        if not invoice:
            raise serializers.ValidationError({"invoice": "Invoice is required."})

        if invoice.status != InvoiceStatus.CONFIRMED:
            raise serializers.ValidationError(
                {"invoice": f"Payments can only be logged against CONFIRMED invoices. Current status is {invoice.status}."}
            )

        amount = attrs.get('amount')
        if amount is not None and amount > invoice.amount_due:
            raise serializers.ValidationError(
                {"amount": f"Payment amount (${amount}) exceeds outstanding balance (${invoice.amount_due})."}
            )

        return attrs


class InvoiceSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_name = serializers.SerializerMethodField(read_only=True)
    subscription_number = serializers.CharField(
        source='subscription.subscription_number',
        read_only=True,
        allow_null=True
    )
    discount_code = serializers.CharField(source='discount.code', read_only=True, allow_null=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'subscription', 'subscription_number',
            'customer', 'customer_email', 'customer_name', 'discount', 'discount_code',
            'status', 'issue_date', 'due_date', 'billing_period_start',
            'billing_period_end', 'subtotal', 'tax_amount', 'discount_amount',
            'total_amount', 'amount_paid', 'amount_due', 'is_overdue',
            'lines', 'payments', 'created_at', 'updated_at'
        )
        read_only_fields = fields

    def get_customer_name(self, obj):
        name = f"{obj.customer.first_name} {obj.customer.last_name}".strip()
        return name or obj.customer.email


# ==========================================
# 7. DASHBOARD SERIALIZERS
# ==========================================

class DashboardOverviewSerializer(serializers.Serializer):
    active_subscription_count = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_outstanding_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    overdue_invoices_count = serializers.IntegerField()
    overdue_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(default="USD")


class DashboardOverdueInvoiceSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    subscription_number = serializers.CharField(source='subscription.subscription_number', read_only=True, allow_null=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'customer', 'customer_email',
            'subscription', 'subscription_number', 'status',
            'issue_date', 'due_date', 'total_amount',
            'amount_paid', 'amount_due', 'days_overdue'
        )

    def get_days_overdue(self, obj):
        today = timezone.localdate()
        if obj.due_date and obj.due_date < today:
            return (today - obj.due_date).days
        return 0


class DashboardPaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    customer_id = serializers.IntegerField(source='invoice.customer_id', read_only=True)
    customer_email = serializers.EmailField(source='invoice.customer.email', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'invoice', 'invoice_number', 'customer_id', 'customer_email',
            'amount', 'payment_date', 'method', 'transaction_reference', 'note'
        )
