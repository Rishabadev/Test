from django.urls import path
from core.views import (
CreateStaffUserView,
InvoiceDetailView,
PasswordResetConfirmView,
PasswordResetRequestView,
SignupView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
# Public Authentication
path('auth/signup/', SignupView.as_view(), name='auth-signup'),
path('auth/login/', TokenObtainPairView.as_view(), name='auth-login'),
path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),


# Admin Protected Management
path('auth/users/create-staff/', CreateStaffUserView.as_view(), name='admin-create-staff'),

# Secured Invoice Endpoint
path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),


]
