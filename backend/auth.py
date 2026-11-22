"""
auth.py — Authentication & Authorization module for ForensicLedger backend.

Dependencies: PyJWT, stdlib only (no Flask imports).
"""

import os
import jwt
import hashlib
import hmac
import datetime
import functools
from typing import Callable, Tuple, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SECRET_KEY: str = os.environ.get("FL_SECRET_KEY", "forensicledger-dev-secret-key-32bytes-secure-hash")
PASSWORD_SALT: str = os.environ.get("FL_PASSWORD_SALT", "forensicledger-salt-dev-salt-32bytes")
TOKEN_EXPIRY: datetime.timedelta = datetime.timedelta(hours=24)
ALGORITHM: str = "HS256"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Raised for all authentication / authorisation failures.

    Attributes:
        message     — human-readable description.
        status_code — HTTP status code that the caller should return
                      (401 for auth failures, 403 for permission failures).
    """

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"AuthError({self.message!r}, status_code={self.status_code})"


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def generate_token(user_id: str, role: str) -> str:
    """Generate a signed JWT for the given *user_id* and *role*.

    The token expires after TOKEN_EXPIRY (default 24 hours).

    Returns:
        A compact, URL-safe JWT string.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + TOKEN_EXPIRY,
    }
    token: str = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    # PyJWT ≥ 2.x returns str; older versions return bytes — normalise.
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token: str) -> dict:
    """Decode and validate a JWT, returning its claims.

    Returns:
        dict with keys ``user_id`` and ``role``.

    Raises:
        AuthError(401) — token is missing, malformed, expired, or has an
                         invalid signature.
    """
    if not token:
        raise AuthError("Token is missing.", status_code=401)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired. Please log in again.", status_code=401)
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}", status_code=401)

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise AuthError("Token payload is incomplete.", status_code=401)

    return {"user_id": user_id, "role": role}


# ---------------------------------------------------------------------------
# Route decorator
# ---------------------------------------------------------------------------

def require_role(*roles: str) -> Callable:
    """Flask route decorator that enforces JWT authentication and role checks.

    Usage::

        @app.route("/api/evidence", methods=["GET"])
        @require_role("investigator", "supervisor")
        def get_evidence():
            ...

    Behaviour:
    - Reads the ``Authorization: Bearer <token>`` header from
      ``flask.request``.
    - Returns HTTP **401** JSON if the header is absent or the token is
      invalid / expired.
    - Returns HTTP **403** JSON if the authenticated role is not in *roles*.
    - On success, injects ``g.current_user = {"user_id": ..., "role": ...}``
      so the view can reference it.

    Note:
        Flask is imported *inside* the decorator at call-time so that this
        module has no hard top-level Flask dependency.
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Lazy Flask import — avoids a hard dependency at module level.
            try:
                from flask import request, jsonify, g  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "require_role decorator requires Flask to be installed."
                ) from exc

            auth_header: Optional[str] = request.headers.get("Authorization", "")
            if not auth_header or not auth_header.startswith("Bearer "):
                return (
                    jsonify({"error": "Authorization header missing or malformed."}),
                    401,
                )

            raw_token = auth_header[len("Bearer "):].strip()
            try:
                claims = decode_token(raw_token)
            except AuthError as err:
                return jsonify({"error": err.message}), err.status_code

            if roles and claims["role"] not in roles:
                return (
                    jsonify(
                        {
                            "error": (
                                f"Access denied. Required role(s): "
                                f"{', '.join(roles)}. "
                                f"Your role: {claims['role']}."
                            )
                        }
                    ),
                    403,
                )

            # Expose claims to the view via Flask's application context.
            g.current_user = claims
            return f(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return a hex-encoded SHA-256 HMAC of *password* using PASSWORD_SALT.

    The salt is read from the ``FL_PASSWORD_SALT`` environment variable (or
    the compile-time default) so that passwords are not trivially reversible
    even if the database is compromised.

    Returns:
        64-character lowercase hex string.
    """
    salted = (PASSWORD_SALT + password).encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time comparison of *password* against its stored *hashed* form.

    Uses :func:`hmac.compare_digest` to prevent timing-based side-channel
    attacks.

    Returns:
        ``True`` if the password matches, ``False`` otherwise.
    """
    expected = hash_password(password)
    return hmac.compare_digest(expected, hashed)


# ---------------------------------------------------------------------------
# Demo user store
# ---------------------------------------------------------------------------
# Passwords are pre-hashed with hash_password() so that plaintext credentials
# are never stored at rest — even in development fixtures.

_DEMO_USERS: dict = {
    "investigator_a": {
        "user_id": "investigator_a",
        "role": "investigator",
        "hashed_password": hash_password("inv123"),
    },
    "investigator_b": {
        "user_id": "investigator_b",
        "role": "investigator",
        "hashed_password": hash_password("inv456"),
    },
    "analyst_a": {
        "user_id": "analyst_a",
        "role": "analyst",
        "hashed_password": hash_password("ana123"),
    },
    "supervisor_a": {
        "user_id": "supervisor_a",
        "role": "supervisor",
        "hashed_password": hash_password("sup123"),
    },
}


# ---------------------------------------------------------------------------
# User authentication
# ---------------------------------------------------------------------------

def authenticate_user(
    username: str, password: str
) -> Optional[Tuple[str, str]]:
    """Verify *username* / *password* against the demo user store.

    Returns:
        ``(user_id, role)`` tuple on success, or ``None`` if the credentials
        are invalid.
    """
    user = _DEMO_USERS.get(username)
    if user is None:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return (user["user_id"], user["role"])
