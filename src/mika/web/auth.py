"""Password hashing and session helpers for the dashboard (single owner account).

Stdlib only: PBKDF2-SHA256 for the password, a signed session cookie for login. The
owner account is stored in ``.env`` (``MIKA_WEB_EMAIL`` / ``MIKA_WEB_PASSWORD`` hash);
when unset, the dashboard offers a first-run "create account" screen.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from starlette.requests import Request

from mika.core.config import get_settings
from mika.core.env_file import write_env

_ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash string safe to store in ``.env``."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a password against a stored hash."""
    try:
        algo, iters, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
    return hmac.compare_digest(check.hex(), digest)


def account_configured() -> bool:
    """True once an owner email + password hash exist."""
    web = get_settings().web
    return bool(web.email and web.password)


def session_secret() -> str:
    """The cookie-signing secret; generate and persist one if missing."""
    secret = get_settings().web.secret
    if secret:
        return secret
    secret = secrets.token_urlsafe(32)
    write_env({"MIKA_WEB_SECRET": secret})
    return secret


def current_user(request: Request) -> str | None:
    """The logged-in owner's email, or None."""
    user = request.session.get("user")
    return user if isinstance(user, str) else None
