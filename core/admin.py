
from django.contrib import admin
from .models import (
    User, TaxRule, Product, ProductVariant, Plan, Discount,
    QuotationTemplate, QuotationTemplateLine,
    Subscription, SubscriptionLine, Invoice, InvoiceLine, Payment,
)

for model in [User, TaxRule, Product, ProductVariant, Plan, Discount,
              QuotationTemplate, QuotationTemplateLine,
              Subscription, SubscriptionLine, Invoice, InvoiceLine, Payment]:
    admin.site.register(model)