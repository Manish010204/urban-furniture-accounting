"""Minimal password hashing (stdlib PBKDF2) - no external auth dependency."""
import hashlib
import hmac
import os

_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(dk.hex(), hash_hex)
