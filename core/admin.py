from django.contrib import admin
from core.models import (
    User,
    TaxRule,
    Product,
    ProductVariant,
    Plan,
    Discount,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
    Invoice,
    InvoiceLine,
    Payment,
)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_type', 'sales_price', 'cost_price', 'is_active')
    list_filter = ('product_type', 'is_active')
    search_fields = ('name', 'notes')
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'attribute_name', 'attribute_value', 'price_extra')
    search_fields = ('product__name', 'attribute_name', 'attribute_value')


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'rate', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'billing_period', 'available_from', 'available_to', 'auto_close_at_end')
    list_filter = ('billing_period', 'auto_close_at_end', 'allow_pause', 'allow_renew')
    search_fields = ('name',)


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'discount_type', 'value', 'start_date', 'end_date',
        'current_uses', 'max_uses', 'is_active'
    )
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
    filter_horizontal = ('products',)


class QuotationTemplateLineInline(admin.TabularInline):
    model = QuotationTemplateLine
    extra = 1


@admin.register(QuotationTemplate)
class QuotationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan', 'validity_days')
    search_fields = ('name', 'plan__name')
    inlines = [QuotationTemplateLineInline]


@admin.register(QuotationTemplateLine)
class QuotationTemplateLineAdmin(admin.ModelAdmin):
    list_display = ('template', 'product', 'variant', 'quantity', 'unit_price')


class SubscriptionLineInline(admin.TabularInline):
    model = SubscriptionLine
    extra = 1


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'subscription_number', 'customer', 'plan', 'status',
        'start_date', 'expiry_date', 'next_billing_date'
    )
    list_filter = ('status', 'start_date')
    search_fields = ('subscription_number', 'customer__email')
    inlines = [SubscriptionLineInline]


@admin.register(SubscriptionLine)
class SubscriptionLineAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'product', 'variant', 'quantity', 'unit_price', 'tax_rule')


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'customer', 'subscription', 'status',
        'issue_date', 'due_date', 'total_amount'
    )
    list_filter = ('status', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'customer__email')
    inlines = [InvoiceLineInline]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'product', 'description', 'quantity', 'unit_price', 'total')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'amount', 'method', 'payment_date', 'transaction_reference')
    list_filter = ('method', 'payment_date')
    search_fields = ('invoice__invoice_number', 'transaction_reference')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
