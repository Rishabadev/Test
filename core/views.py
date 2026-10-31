"""
core/views.py - Auth endpoints, protected invoice retrieval,
and ViewSets for Products, Taxes, Plans, Discounts, Quotes, Subscriptions, Invoices, and Payments.
"""

from datetime import datetime, time
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
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
)
from core.permissions import IsAdmin, IsCustomerOwner, IsStaffOrAdmin
from core.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
    StaffUserCreateSerializer,
    CurrentUserSerializer,
    TaxRuleSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    PlanSerializer,
    DiscountSerializer,
    QuotationTemplateSerializer,
    QuotationTemplateLineSerializer,
    SubscriptionSerializer,
    SubscriptionLineSerializer,
    InvoiceSerializer,
    InvoiceLineSerializer,
    PaymentSerializer,
    DashboardOverviewSerializer,
    DashboardOverdueInvoiceSerializer,
    DashboardPaymentSerializer,
)
from core.utils import generate_invoice_pdf, generate_subscription_number

User = get_user_model()


# ==========================================
# 1. AUTHENTICATION VIEWS
# ==========================================

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


class CurrentUserView(APIView):
    """
    GET /api/auth/me/
    Returns {id, email, first_name, last_name, role} for the logged-in user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
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
    Legacy named route: demonstrates multi-tenant isolation.
    Customers receive 404/403 if inspecting another customer's invoice.
    """
    permission_classes = [IsAuthenticated, IsCustomerOwner]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related('customer', 'subscription', 'discount').prefetch_related(
            'lines__product', 'payments'
        )
        if user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return qs.all()
        return qs.filter(customer=user)


# ==========================================
# 2. CATALOG VIEWSETS (ADMIN-WRITE, STAFF-READ)
# ==========================================

class TaxRuleViewSet(viewsets.ModelViewSet):
    """
    Tax rules: admin-only write, staff read.
    """
    queryset = TaxRule.objects.all().order_by('name')
    serializer_class = TaxRuleSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAdmin()]
        return [IsAdmin()]


class ProductViewSet(viewsets.ModelViewSet):
    """
    Products with variants: admin-only write, staff read.
    """
    queryset = Product.objects.all().prefetch_related('variants').order_by('id')
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAdmin()]
        return [IsAdmin()]


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    Product variants: admin-only write, staff read.
    """
    queryset = ProductVariant.objects.all().select_related('product').order_by('id')
    serializer_class = ProductVariantSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAdmin()]
        return [IsAdmin()]


class PlanViewSet(viewsets.ModelViewSet):
    """
    Plans: admin-only write, staff read.
    """
    queryset = Plan.objects.all().order_by('id')
    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAdmin()]
        return [IsAdmin()]


class DiscountViewSet(viewsets.ModelViewSet):
    """
    Discounts: admin-only for create/update/delete, staff read.
    """
    queryset = Discount.objects.all().prefetch_related('products').order_by('id')
    serializer_class = DiscountSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsStaffOrAdmin()]
        return [IsAdmin()]


# ==========================================
# 3. QUOTATION TEMPLATE VIEWSETS (STAFF & ADMIN)
# ==========================================

class QuotationTemplateViewSet(viewsets.ModelViewSet):
    """
    Quotation templates with lines: Staff and admin can create and manage them.
    """
    queryset = QuotationTemplate.objects.all().select_related('plan').prefetch_related('lines__product', 'lines__variant').order_by('id')
    serializer_class = QuotationTemplateSerializer
    permission_classes = [IsStaffOrAdmin]

    @action(detail=True, methods=['post'], url_path='create-subscription', permission_classes=[IsStaffOrAdmin])
    def create_subscription(self, request, pk=None):
        template = self.get_object()
        customer_id = request.data.get('customer') or request.data.get('customer_id')

        if not customer_id:
            return Response({"customer": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            customer = User.objects.get(pk=customer_id, role=UserRole.CUSTOMER)
        except User.DoesNotExist:
            return Response({"customer": ["Customer not found or user is not a customer."]}, status=status.HTTP_400_BAD_REQUEST)

        start_date_val = request.data.get('start_date')
        if start_date_val:
            if isinstance(start_date_val, str):
                start_date = parse_date(start_date_val)
                if not start_date:
                    return Response({"start_date": ["Invalid date format. Use YYYY-MM-DD."]}, status=status.HTTP_400_BAD_REQUEST)
            else:
                start_date = start_date_val
        else:
            start_date = timezone.localdate()

        discount = None
        discount_id = request.data.get('discount') or request.data.get('discount_id')
        if discount_id:
            try:
                discount = Discount.objects.get(pk=discount_id)
            except Discount.DoesNotExist:
                return Response({"discount": ["Discount not found."]}, status=status.HTTP_400_BAD_REQUEST)

        payment_terms_days = request.data.get('payment_terms_days', 30)
        try:
            payment_terms_days = int(payment_terms_days)
        except (TypeError, ValueError):
            payment_terms_days = 30

        expiry_date = start_date + timezone.timedelta(days=template.validity_days)

        with transaction.atomic():
            subscription = Subscription.objects.create(
                subscription_number=generate_subscription_number(start_date),
                customer=customer,
                plan=template.plan,
                discount=discount,
                status=SubscriptionStatus.DRAFT,
                start_date=start_date,
                expiry_date=expiry_date,
                payment_terms_days=payment_terms_days,
            )

            lines_to_create = []
            for t_line in template.lines.all():
                price_extra = t_line.variant.price_extra if t_line.variant else Decimal('0.00')
                unit_price = t_line.product.sales_price + price_extra
                lines_to_create.append(
                    SubscriptionLine(
                        subscription=subscription,
                        product=t_line.product,
                        variant=t_line.variant,
                        quantity=t_line.quantity,
                        unit_price=unit_price
                    )
                )
            if lines_to_create:
                SubscriptionLine.objects.bulk_create(lines_to_create)

        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)


class QuotationTemplateLineViewSet(viewsets.ModelViewSet):
    """
    Quotation template lines: Staff and admin can manage them.
    """
    queryset = QuotationTemplateLine.objects.all().select_related('template', 'product', 'variant').order_by('id')
    serializer_class = QuotationTemplateLineSerializer
    permission_classes = [IsStaffOrAdmin]


# ==========================================
# 4. SUBSCRIPTION VIEWSETS
# ==========================================

class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    Subscriptions with lines.
    Staff and admin create and edit. Customers can only list and view their own.
    Auto-generates subscription_number like SUB-2026-0001.
    Unit price = product.sales_price + variant.price_extra.
    Actions:
    - /transition/: transitions status with validation; 400 on invalid jump;
      when moving to ACTIVE, next_billing_date = start_date.
    - /create-from-template/: generates subscription and lines from QuotationTemplate.
    """
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Subscription.objects.none()

        qs = Subscription.objects.select_related(
            'customer', 'plan', 'discount'
        ).prefetch_related(
            'lines__product', 'lines__variant', 'lines__tax_rule'
        ).order_by('-created_at')

        if user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return qs.all()
        # Customers can only list and view their own
        return qs.filter(customer=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsCustomerOwner()]
        return [IsStaffOrAdmin()]

    @action(detail=True, methods=['post'], url_path='transition', permission_classes=[IsStaffOrAdmin])
    def transition(self, request, pk=None):
        subscription = self.get_object()
        target_status = request.data.get('status') or request.data.get('new_status')

        if not target_status:
            return Response(
                {"detail": "Field 'status' or 'new_status' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if target_status not in SubscriptionStatus.values:
            return Response(
                {"detail": f"'{target_status}' is not a valid subscription status choice."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subscription.transition_to(target_status)
            if subscription.status == SubscriptionStatus.ACTIVE:
                subscription.next_billing_date = subscription.start_date
                subscription.save(update_fields=['next_billing_date', 'updated_at'])
        except (DjangoValidationError, DRFValidationError) as exc:
            msg = exc.messages if hasattr(exc, 'messages') else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='create-from-template', permission_classes=[IsStaffOrAdmin])
    def create_from_template(self, request):
        template_id = request.data.get('template') or request.data.get('template_id')
        customer_id = request.data.get('customer') or request.data.get('customer_id')

        if not template_id:
            return Response({"template": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if not customer_id:
            return Response({"customer": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            template = QuotationTemplate.objects.select_related('plan').prefetch_related(
                'lines__product', 'lines__variant'
            ).get(pk=template_id)
        except QuotationTemplate.DoesNotExist:
            return Response({"template": ["Quotation template not found."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            customer = User.objects.get(pk=customer_id, role=UserRole.CUSTOMER)
        except User.DoesNotExist:
            return Response({"customer": ["Customer not found or user is not a customer."]}, status=status.HTTP_400_BAD_REQUEST)

        start_date_val = request.data.get('start_date')
        if start_date_val:
            if isinstance(start_date_val, str):
                start_date = parse_date(start_date_val)
                if not start_date:
                    return Response({"start_date": ["Invalid date format. Use YYYY-MM-DD."]}, status=status.HTTP_400_BAD_REQUEST)
            else:
                start_date = start_date_val
        else:
            start_date = timezone.localdate()

        discount = None
        discount_id = request.data.get('discount') or request.data.get('discount_id')
        if discount_id:
            try:
                discount = Discount.objects.get(pk=discount_id)
            except Discount.DoesNotExist:
                return Response({"discount": ["Discount not found."]}, status=status.HTTP_400_BAD_REQUEST)

        payment_terms_days = request.data.get('payment_terms_days', 30)
        try:
            payment_terms_days = int(payment_terms_days)
        except (TypeError, ValueError):
            payment_terms_days = 30

        expiry_date = start_date + timezone.timedelta(days=template.validity_days)

        with transaction.atomic():
            subscription = Subscription.objects.create(
                subscription_number=generate_subscription_number(start_date),
                customer=customer,
                plan=template.plan,
                discount=discount,
                status=SubscriptionStatus.DRAFT,
                start_date=start_date,
                expiry_date=expiry_date,
                payment_terms_days=payment_terms_days,
            )

            lines_to_create = []
            for t_line in template.lines.all():
                price_extra = t_line.variant.price_extra if t_line.variant else Decimal('0.00')
                unit_price = t_line.product.sales_price + price_extra
                lines_to_create.append(
                    SubscriptionLine(
                        subscription=subscription,
                        product=t_line.product,
                        variant=t_line.variant,
                        quantity=t_line.quantity,
                        unit_price=unit_price
                    )
                )
            if lines_to_create:
                SubscriptionLine.objects.bulk_create(lines_to_create)

        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='create_from_template', permission_classes=[IsStaffOrAdmin])
    def create_from_template_alias(self, request):
        return self.create_from_template(request)


class SubscriptionLineViewSet(viewsets.ModelViewSet):
    """
    Subscription lines.
    Staff and admin create and edit. Customers can only list and view their own.
    Unit price = product.sales_price + variant.price_extra.
    """
    serializer_class = SubscriptionLineSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return SubscriptionLine.objects.none()

        qs = SubscriptionLine.objects.select_related(
            'subscription', 'product', 'variant', 'tax_rule'
        ).order_by('id')

        if user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return qs.all()
        return qs.filter(subscription__customer=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsCustomerOwner()]
        return [IsStaffOrAdmin()]


# ==========================================
# 5. INVOICE VIEWSETS
# ==========================================

class InvoiceViewSet(viewsets.ModelViewSet):
    """
    Invoices endpoint.
    - Customers can only list and view their own invoices.
    - Staff and Admin can view all invoices, confirm, cancel, send, and log payments.
    - Actions:
      * POST /api/invoices/{id}/confirm/
      * POST /api/invoices/{id}/cancel/
      * POST /api/invoices/{id}/send/ (console email)
      * GET  /api/invoices/{id}/pdf/ (PDF print)
      * GET  /api/invoices/{id}/print/ (PDF print alias)
      * POST /api/invoices/{id}/pay/ (Staff/Admin payment)
    """
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Invoice.objects.none()

        qs = Invoice.objects.select_related(
            'customer', 'subscription', 'discount'
        ).prefetch_related(
            'lines__product', 'payments'
        ).order_by('-issue_date', '-id')

        if user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return qs.all()
        # Customers can only view their own invoices
        return qs.filter(customer=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'pdf', 'pdf_print']:
            return [IsCustomerOwner()]
        return [IsStaffOrAdmin()]

    @action(detail=True, methods=['post'], url_path='confirm', permission_classes=[IsStaffOrAdmin])
    def confirm(self, request, pk=None):
        invoice = self.get_object()
        try:
            invoice.transition_to(InvoiceStatus.CONFIRMED)
        except DjangoValidationError as exc:
            msg = exc.messages if hasattr(exc, 'messages') else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsStaffOrAdmin])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        try:
            invoice.transition_to(InvoiceStatus.CANCELLED)
        except DjangoValidationError as exc:
            msg = exc.messages if hasattr(exc, 'messages') else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='send', permission_classes=[IsStaffOrAdmin])
    def send_invoice(self, request, pk=None):
        invoice = self.get_object()
        subject = f"Invoice {invoice.invoice_number} from Brightloop Software"
        message = (
            f"Dear {invoice.customer.first_name or invoice.customer.email},\n\n"
            f"Please find your invoice details below:\n"
            f"Invoice Number: {invoice.invoice_number}\n"
            f"Issue Date:     {invoice.issue_date}\n"
            f"Due Date:       {invoice.due_date}\n"
            f"Total Amount:   ${invoice.total_amount}\n"
            f"Status:         {invoice.status}\n\n"
            f"Thank you for your business!\n"
            f"Brightloop Software Team"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.customer.email],
            fail_silently=False,
        )
        return Response(
            {"detail": f"Invoice {invoice.invoice_number} sent to {invoice.customer.email}."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='pdf', permission_classes=[IsCustomerOwner])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        pdf_bytes = generate_invoice_pdf(invoice)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.invoice_number}.pdf"'
        return response

    @action(detail=True, methods=['get'], url_path='print', permission_classes=[IsCustomerOwner])
    def pdf_print(self, request, pk=None):
        return self.pdf(request, pk=pk)

    @action(detail=True, methods=['post'], url_path='pay', permission_classes=[IsStaffOrAdmin])
    def pay(self, request, pk=None):
        invoice = self.get_object()
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data['invoice'] = invoice.id
        serializer = PaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = serializer.save()
        except DjangoValidationError as exc:
            msg = exc.messages if hasattr(exc, 'messages') else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


# ==========================================
# 6. PAYMENT VIEWSET (POST ONLY, STAFF/ADMIN)
# ==========================================

class PaymentViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """
    Payment endpoint: POST only, restricted to Staff and Admins.
    Uses concurrency-safe row-level locking on Payment.save().
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsStaffOrAdmin]
    http_method_names = ['post', 'head', 'options']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = serializer.save()
        except DjangoValidationError as exc:
            msg = exc.messages if hasattr(exc, 'messages') else str(exc)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


# ==========================================
# 7. FINANCE DASHBOARD VIEWSET (STAFF/ADMIN ONLY)
# ==========================================

class DashboardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class DashboardViewSet(viewsets.ViewSet):
    """
    Finance dashboard endpoints under /api/dashboard/ (Staff & Admin only).
    Metrics:
    - active subscription count
    - total revenue (sum of payments)
    - outstanding amount (invoices - payments)
    - overdue invoices count and amount (CONFIRMED, due_date < today, unpaid)
    - payments list
    Filters: date range (start_date/end_date), status, customer, method.
    Uses aggregate queries, select_related, pagination, and existing indexes.
    """
    permission_classes = [IsStaffOrAdmin]
    pagination_class = DashboardPagination

    def _parse_filters(self, request):
        params = request.query_params
        start_date_str = params.get('start_date') or params.get('from_date')
        end_date_str = params.get('end_date') or params.get('to_date')
        customer_val = params.get('customer') or params.get('customer_id')
        status_val = params.get('status')
        method = params.get('method')

        parsed_start = parse_date(start_date_str) if start_date_str else None
        parsed_end = parse_date(end_date_str) if end_date_str else None

        customer_id = None
        if customer_val:
            try:
                customer_id = int(customer_val)
            except ValueError:
                c_user = User.objects.filter(email=customer_val).first()
                if c_user:
                    customer_id = c_user.id

        return {
            'start_date': parsed_start,
            'end_date': parsed_end,
            'customer_id': customer_id,
            'status': status_val,
            'method': method,
        }

    def list(self, request):
        """GET /api/dashboard/ -> High-level financial KPIs overview."""
        return self.overview(request)

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        """GET /api/dashboard/overview/ -> High-level financial KPIs overview."""
        filters = self._parse_filters(request)
        today = timezone.localdate()

        # 1. Active Subscriptions Count (Index: ['customer', 'status'])
        sub_qs = Subscription.objects.all()
        if filters['customer_id']:
            sub_qs = sub_qs.filter(customer_id=filters['customer_id'])
        if filters['start_date']:
            sub_qs = sub_qs.filter(start_date__gte=filters['start_date'])
        if filters['end_date']:
            sub_qs = sub_qs.filter(start_date__lte=filters['end_date'])

        if filters['status']:
            active_count = sub_qs.filter(status=filters['status']).count()
        else:
            active_count = sub_qs.filter(status=SubscriptionStatus.ACTIVE).count()

        # 2. Total Revenue (Sum of payments, Index: ['invoice', 'payment_date'])
        payment_qs = Payment.objects.all()
        if filters['customer_id']:
            payment_qs = payment_qs.filter(invoice__customer_id=filters['customer_id'])
        if filters['start_date']:
            start_dt = timezone.make_aware(datetime.combine(filters['start_date'], time.min))
            payment_qs = payment_qs.filter(payment_date__gte=start_dt)
        if filters['end_date']:
            end_dt = timezone.make_aware(datetime.combine(filters['end_date'], time.max))
            payment_qs = payment_qs.filter(payment_date__lte=end_dt)
        if filters['method']:
            payment_qs = payment_qs.filter(method=filters['method'])

        total_revenue = payment_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 3. Outstanding Amount (on open, non-cancelled invoices)
        inv_qs = Invoice.objects.exclude(status=InvoiceStatus.CANCELLED)
        if filters['customer_id']:
            inv_qs = inv_qs.filter(customer_id=filters['customer_id'])
        if filters['start_date']:
            inv_qs = inv_qs.filter(issue_date__gte=filters['start_date'])
        if filters['end_date']:
            inv_qs = inv_qs.filter(issue_date__lte=filters['end_date'])

        if filters['status']:
            inv_qs = inv_qs.filter(status=filters['status'])
        else:
            # Default to confirmed open invoices
            inv_qs = inv_qs.filter(status__in=[InvoiceStatus.CONFIRMED, InvoiceStatus.DRAFT])

        inv_total_sum = inv_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        inv_paid_sum = Payment.objects.filter(invoice__in=inv_qs).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        outstanding_amount = max(Decimal('0.00'), inv_total_sum - inv_paid_sum)

        # 4. Overdue Invoices (CONFIRMED, due_date < today, unpaid)
        # Leverages existing index: ['status', 'due_date']
        overdue_qs = Invoice.objects.filter(
            status=InvoiceStatus.CONFIRMED,
            due_date__lt=today
        )
        if filters['customer_id']:
            overdue_qs = overdue_qs.filter(customer_id=filters['customer_id'])
        if filters['start_date']:
            overdue_qs = overdue_qs.filter(issue_date__gte=filters['start_date'])
        if filters['end_date']:
            overdue_qs = overdue_qs.filter(issue_date__lte=filters['end_date'])

        overdue_invoiced = overdue_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        overdue_paid = Payment.objects.filter(invoice__in=overdue_qs).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        overdue_amount = max(Decimal('0.00'), overdue_invoiced - overdue_paid)
        overdue_invoices_count = overdue_qs.count()

        data = {
            'active_subscription_count': active_count,
            'total_revenue': total_revenue,
            'total_outstanding_amount': outstanding_amount,
            'overdue_invoices_count': overdue_invoices_count,
            'overdue_amount': overdue_amount,
            'currency': 'USD',
        }
        return Response(DashboardOverviewSerializer(data).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='overdue-invoices')
    def overdue_invoices(self, request):
        """GET /api/dashboard/overdue-invoices/ -> Paginated list of overdue invoices."""
        filters = self._parse_filters(request)
        today = timezone.localdate()

        # Query uses existing ['status', 'due_date'] index and select_related
        qs = (
            Invoice.objects.filter(
                status=InvoiceStatus.CONFIRMED,
                due_date__lt=today
            )
            .select_related('customer', 'subscription')
            .order_by('due_date', 'id')
        )

        if filters['customer_id']:
            qs = qs.filter(customer_id=filters['customer_id'])
        if filters['start_date']:
            qs = qs.filter(issue_date__gte=filters['start_date'])
        if filters['end_date']:
            qs = qs.filter(issue_date__lte=filters['end_date'])

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = DashboardOverdueInvoiceSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='payments')
    def payments(self, request):
        """GET /api/dashboard/payments/ -> Paginated list of payments."""
        filters = self._parse_filters(request)

        # Query uses existing ['invoice', 'payment_date'] index and select_related
        qs = (
            Payment.objects.select_related('invoice', 'invoice__customer')
            .order_by('-payment_date', '-id')
        )

        if filters['customer_id']:
            qs = qs.filter(invoice__customer_id=filters['customer_id'])
        if filters['start_date']:
            start_dt = timezone.make_aware(datetime.combine(filters['start_date'], time.min))
            qs = qs.filter(payment_date__gte=start_dt)
        if filters['end_date']:
            end_dt = timezone.make_aware(datetime.combine(filters['end_date'], time.max))
            qs = qs.filter(payment_date__lte=end_dt)
        if filters['method']:
            qs = qs.filter(method=filters['method'])

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = DashboardPaymentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ==========================================
# 7. FRONTEND TEMPLATE VIEWS
# ==========================================

def login_view(request):
    """Renders the SaaS login page."""
    return render(request, 'auth/login.html')


def signup_view(request):
    """Renders the SaaS signup page."""
    return render(request, 'auth/signup.html')


def dashboard_view(request):
    """Placeholder view for Admin & Staff dashboard landing."""
    return render(request, 'dashboard/index.html')


def portal_view(request):
    """Renders the Customer Portal application."""
    return render(request, 'portal/customer-portal.html')


def products_view(request):
    """Renders the Products & Variant Management module for Admins."""
    return render(request, 'products/products.html')


