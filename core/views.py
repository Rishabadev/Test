from django.shortcuts import render

# Create your views here.
"""
core/views.py - Auth endpoints and protected invoice retrieval.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Invoice, UserRole
from core.permissions import IsAdmin, IsCustomerOwner
from core.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
    StaffUserCreateSerializer,
)

User = get_user_model()


class SignupView(generics.CreateAPIView):
    """
    POST /api/auth/signup/
    Public registration endpoint. Always creates an account with CUSTOMER role.
    """
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]


class CreateStaffUserView(generics.CreateAPIView):
    """
    POST /api/auth/users/create-staff/
    Restricted endpoint: Only Admins can provision Staff users.
    """
    serializer_class = StaffUserCreateSerializer
    permission_classes = [IsAdmin]


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/
    Generates a cryptographically signed, one-time-use token and sends an email.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email, is_active=True)
            # Token is salted with the user's password hash; changing password invalidates it
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Frontend React route: /reset-password?uid=...&token=...
            reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uidb64}&token={token}"

            send_mail(
                subject="Reset your Brightloop Software Password",
                message=(
                    f"Hello {user.first_name or 'there'},\n\n"
                    f"Use the link below to reset your password. It will expire shortly:\n"
                    f"{reset_url}\n\n"
                    f"If you did not request this, you can safely ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except User.DoesNotExist:
            # Mask user existence to prevent account enumeration attacks
            pass

        return Response(
            {"detail": "If an account exists with this email, a reset link has been dispatched."},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset/confirm/
    Verifies uidb64 + token and commits the new password.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been reset successfully. You may now log in."},
            status=status.HTTP_200_OK
        )


class InvoiceDetailView(generics.RetrieveAPIView):
    """
    GET /api/invoices/<id>/
    Demonstrates multi-tenant isolation.
    Customers receive a 404 (or 403) if attempting to inspect another customer's invoice.
    """
    permission_classes = [IsAuthenticated, IsCustomerOwner]

    def get_queryset(self):
        user = self.request.user

        # Admins and Staff view the complete catalog of invoices
        if user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return Invoice.objects.all().select_related('customer')

        # Customers are restricted to invoices where they are the designated debtor
        return Invoice.objects.filter(customer=user).select_related('customer')

    def get_serializer_class(self):
        # Minimal inline serializer for demonstration
        from rest_framework import serializers

        class InvoiceDetailSerializer(serializers.ModelSerializer):
            class Meta:
                model = Invoice
                fields = (
                    'id', 'invoice_number', 'status', 'issue_date',
                    'due_date', 'subtotal', 'tax_amount', 'discount_amount',
                    'total_amount'
                )

        return InvoiceDetailSerializer