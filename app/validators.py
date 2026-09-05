import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PINCODE_RE = re.compile(r"^\d{4,10}$")
LOGIN_ID_RE = re.compile(r"^[A-Za-z0-9_]{6,12}$")
PASSWORD_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


class ValidationError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def require(condition: bool, message: str):
    if not condition:
        raise ValidationError(message)


def validate_email(email: str | None):
    if email and not EMAIL_RE.match(email):
        raise ValidationError("Please enter a valid email address.")


def validate_pincode(pincode: str | None):
    if pincode and not PINCODE_RE.match(pincode):
        raise ValidationError("Pincode should be 4-10 digits.")


def validate_login_id(login_id: str):
    if not LOGIN_ID_RE.match(login_id or ""):
        raise ValidationError("Login ID must be 6-12 characters (letters, digits, underscore).")


def validate_password_strength(password: str):
    password = password or ""
    if len(password) <= 8:
        raise ValidationError("Password must be more than 8 characters.")
    if not any(c.islower() for c in password):
        raise ValidationError("Password must contain a lowercase letter.")
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain an uppercase letter.")
    if not PASSWORD_SPECIAL_RE.search(password):
        raise ValidationError("Password must contain a special character.")
