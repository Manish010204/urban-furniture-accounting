import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PINCODE_RE = re.compile(r"^\d{4,10}$")


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
