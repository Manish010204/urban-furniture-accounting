"""Environment-based configuration. Reads a local .env file (if present, via
python-dotenv) then falls back to real environment variables — no secrets are
hardcoded in source. See .env.example for the variables this app reads."""
import os

from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY environment variable must be set when ENVIRONMENT=production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    # Local-development-only fallback so the app still runs without a .env file.
    # Never used when ENVIRONMENT=production (see above).
    SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"

SESSION_MAX_AGE_SECONDS = int(os.environ.get("SESSION_MAX_AGE_SECONDS", str(8 * 60 * 60)))

LOGIN_MAX_FAILED_ATTEMPTS = int(os.environ.get("LOGIN_MAX_FAILED_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))
