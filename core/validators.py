"""
core/validators.py - Custom password strength validation for Brightloop Software.
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    """
    Enforces Brightloop password rules:
    - Minimum length: strictly greater than 8 characters (>= 9 characters)
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one special symbol (!, @, #, etc.)
    """

    def __init__(self, min_length=9):
        self.min_length = min_length

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _(f"Password must be longer than 8 characters (at least {self.min_length} characters)."),
                code='password_too_short',
            )

        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter (A-Z)."),
                code='password_no_upper',
            )

        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter (a-z)."),
                code='password_no_lower',
            )

        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError(
                _("Password must contain at least one special character (!, @, #, $, etc.)."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _(
            "Your password must be longer than 8 characters and contain at least "
            "one uppercase letter, one lowercase letter, and one special character."
        )