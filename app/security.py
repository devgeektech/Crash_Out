"""
Password hashing + reversible encryption for API secrets.

- Passwords: bcrypt (one-way hash; never reversible)
- Vidu API keys: Fernet (AES) so they can be decrypted for live API calls
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import os
from typing import Any, Dict, Optional

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from dotenv import set_key

try:
    import jwt  # type: ignore
except ImportError:
    jwt = None  # type: ignore

from app.config import ENV_PATH


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            (password_hash or "").encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _persist_env(key: str, value: str) -> None:
    try:
        set_key(ENV_PATH, key, value)
    except Exception:
        pass
    os.environ[key] = value


def session_secret() -> str:
    """Signed cookie secret for SessionMiddleware."""
    existing = (os.getenv("AUTH_SECRET_KEY") or "").strip()
    if existing:
        return existing
    generated = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    _persist_env("AUTH_SECRET_KEY", generated)
    return generated


def create_access_token(user_id: int, email: str, expires_delta_hours: int = 24) -> str:
    """Generate a signed JWT access token for user authentication."""
    secret = session_secret()
    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(hours=expires_delta_hours)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": expire,
    }
    if jwt is not None:
        return jwt.encode(payload, secret, algorithm="HS256")

    # Pure standard library fallback (HMAC-SHA256) if jwt is not loaded
    import hmac
    import json

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    exp_ts = int(expire.timestamp())
    iat_ts = int(now.timestamp())
    raw_payload = _b64url(
        json.dumps({"sub": str(user_id), "email": email, "iat": iat_ts, "exp": exp_ts}).encode("utf-8")
    )
    msg = f"{header}.{raw_payload}".encode("ascii")
    sig = _b64url(hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest())
    return f"{header}.{raw_payload}.{sig}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate and decode a signed JWT access token."""
    secret = session_secret()
    if jwt is not None:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            return None

    # Pure standard library fallback (HMAC-SHA256)
    import hmac
    import json

    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        def _b64dec(s: str) -> bytes:
            padding = "=" * ((4 - len(s) % 4) % 4)
            return base64.urlsafe_b64decode(s + padding)

        msg = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
        ).rstrip(b"=").decode("ascii")

        if not hmac.compare_digest(sig_b64, expected_sig):
            return None

        payload = json.loads(_b64dec(payload_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp and datetime.datetime.now(datetime.timezone.utc).timestamp() > float(exp):
            return None
        return payload
    except Exception:
        return None


def _fernet_key() -> bytes:
    raw = (os.getenv("SECRET_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            # Accept either a Fernet key or any passphrase (derive).
            if len(raw) == 44 and raw.endswith("="):
                return raw.encode("ascii")
            digest = hashlib.sha256(raw.encode("utf-8")).digest()
            return base64.urlsafe_b64encode(digest)
        except Exception:
            pass
    generated = Fernet.generate_key().decode("ascii")
    _persist_env("SECRET_ENCRYPTION_KEY", generated)
    return generated.encode("ascii")


def _fernet() -> Fernet:
    return Fernet(_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    value = (plaintext or "").strip()
    if not value:
        return ""
    token = _fernet().encrypt(value.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        return ""
    try:
        return _fernet().decrypt(raw.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def mask_secret(value: Optional[str], keep: int = 4) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= keep:
        return "•" * len(text)
    return ("•" * max(8, len(text) - keep)) + text[-keep:]
