"""
core/permissions.py - Role-based and object-level permission classes.
"""

from rest_framework.permissions import BasePermission
from core.models import UserRole


class IsAdmin(BasePermission):
    """Allows access exclusively to Admin accounts."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.ADMIN
        )


class IsStaffOrAdmin(BasePermission):
    """Allows access to internal Staff and Admins."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in [UserRole.STAFF, UserRole.ADMIN]
        )


class IsCustomerOwner(BasePermission):
    """
    Object-level permission:
    - Staff and Admins can access any record.
    - Customers can only read and access objects where obj.customer == request.user.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Admins and Staff bypass ownership restrictions
        if request.user.role in [UserRole.ADMIN, UserRole.STAFF]:
            return True

        # For models linked to a customer (Invoices, Subscriptions)
        if hasattr(obj, 'customer'):
            return obj.customer_id == request.user.id

        # For the User model itself (e.g. editing their own profile)
        return obj == request.user