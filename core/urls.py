from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.views import (
    CreateStaffUserView,
    CurrentUserView,
    InvoiceDetailView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    SignupView,
    ProductViewSet,
    ProductVariantViewSet,
    TaxRuleViewSet,
    PlanViewSet,
    DiscountViewSet,
    QuotationTemplateViewSet,
    QuotationTemplateLineViewSet,
    SubscriptionViewSet,
    SubscriptionLineViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    DashboardViewSet,
)

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('product-variants', ProductVariantViewSet, basename='product-variant')
router.register('tax-rules', TaxRuleViewSet, basename='tax-rule')
router.register('plans', PlanViewSet, basename='plan')
router.register('discounts', DiscountViewSet, basename='discount')
router.register('quotation-templates', QuotationTemplateViewSet, basename='quotation-template')
router.register('quotation-template-lines', QuotationTemplateLineViewSet, basename='quotation-template-line')
router.register('subscriptions', SubscriptionViewSet, basename='subscription')
router.register('subscription-lines', SubscriptionLineViewSet, basename='subscription-line')
router.register('invoices', InvoiceViewSet, basename='invoice')
router.register('payments', PaymentViewSet, basename='payment')
router.register('dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    # Public Authentication
    path('auth/signup/', SignupView.as_view(), name='auth-signup'),
    path('auth/login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),

    # Admin Protected Management
    path('auth/users/create-staff/', CreateStaffUserView.as_view(), name='admin-create-staff'),

    # Secured Invoice Endpoint (legacy detail route)
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),

    # API ViewSets
    path('', include(router.urls)),
]
